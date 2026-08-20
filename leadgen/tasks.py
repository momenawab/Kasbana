"""Celery entry points for lead generation.

Two things live here that are not in ``services.jobs``: which queue a job runs
on, and what happens when there is no broker to run it on.

Priority is a *queue* choice rather than a sort order (see settings): a
1,000-result background sweep must never delay a job a rep is watching, and a
worker can be pointed at ``leadgen_high`` alone when that matters.

The synchronous fallback exists so the pipeline can be exercised on a machine
with no Redis. It is deliberately narrow — it triggers only on a broker
connection failure, never on a task error — because silently running a job
in-process when the broker is *merely slow* would turn a queueing problem into
a request timeout.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone
from kombu.exceptions import OperationalError

from leadgen import enums
from leadgen.models import SearchJob
from leadgen.services import jobs as job_service

logger = logging.getLogger(__name__)

QUEUE_FOR_PRIORITY: dict[str, str] = {
    enums.JobPriority.HIGH: "leadgen_high",
    enums.JobPriority.NORMAL: "leadgen",
    enums.JobPriority.BACKGROUND: "leadgen_bg",
}


@shared_task(
    name="leadgen.tasks.run_search_job",
    queue="leadgen",
    bind=True,
    max_retries=2,
    # Only infrastructure faults are retried. A misconfigured job or a rejected
    # API key fails identically on every attempt, and ``jobs.run`` has already
    # recorded the reason on the job by the time we get here.
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
)
def run_search_job(self, job_id: str) -> dict:
    """Run one search job to completion."""
    job = SearchJob.objects.filter(pk=job_id).first()
    if job is None:
        logger.warning("leadgen.task.job_missing", extra={"job": job_id})
        return {"job": job_id, "status": "missing"}

    job = job_service.run(job)
    return {
        "job": str(job.id),
        "status": job.status,
        "discovered": job.discovered_count,
        "ready": job.ready_count,
        "failed": job.failed_count,
    }


def consumers_for(queue: str) -> int | None:
    """How many workers are consuming ``queue``. None when that can't be determined.

    Publishing to a queue nobody consumes succeeds — the broker accepts the
    message and it waits forever. From the publisher's side that is
    indistinguishable from a healthy enqueue, which is exactly how a job can sit
    at "Queued" indefinitely with nothing in any log to say why. Asking the
    workers directly is the only way to tell the two apart.
    """
    try:
        from config.celery import app

        active = app.control.inspect(timeout=1.5).active_queues()
    except Exception as exc:  # noqa: BLE001 — inspect fails in many uninteresting ways
        logger.warning("leadgen.enqueue.inspect_failed", extra={"error": str(exc)})
        return None

    if active is None:
        return 0  # broker reachable, nobody answered → no workers at all
    return sum(1 for queues in active.values() if any(q.get("name") == queue for q in queues))


def enqueue(job: SearchJob) -> str:
    """Queue ``job``. Returns "queued", "inline", or "unconsumed".

    Three outcomes, because there are three genuinely different situations and
    collapsing them is what hid this bug in the first place:

    * **queued** — a worker is listening; the job will run.
    * **inline** — no broker at all. Expected on a developer machine, so the
      pipeline runs in-process rather than blocking local work.
    * **unconsumed** — the broker took the message but no worker consumes that
      queue. The job is failed immediately with a message naming the queue,
      rather than waiting forever.

    The last case deliberately does *not* fall back to running inline. A
    1,000-result sweep takes minutes; running it inside the request that created
    it would hang the browser and time out the gateway. Failing loudly with the
    queue name is both safer and more useful — it names the fix.
    """
    queue = QUEUE_FOR_PRIORITY.get(job.priority, "leadgen")

    try:
        run_search_job.apply_async(args=[str(job.id)], queue=queue)
    except OperationalError as exc:
        # No broker. Expected on a developer machine; alarming in production,
        # hence the error-level log either way.
        logger.error("leadgen.enqueue.no_broker", extra={"job": str(job.id), "error": str(exc)})
        job_service.log(
            job,
            "No Celery broker reachable — running synchronously",
            level=enums.LogLevel.WARNING,
        )
        job_service.run(job)
        return "inline"

    # None means we could not ask, which is not evidence of a problem — leave the
    # job queued rather than failing a healthy one on a flaky inspect.
    consumers = consumers_for(queue)
    if consumers == 0:
        message = (
            f"No Celery worker is consuming the “{queue}” queue, so this job would "
            f"wait forever. Start a worker with -Q {queue} (see infra/compose.prod.yml)."
        )
        logger.error("leadgen.enqueue.no_consumer", extra={"job": str(job.id), "queue": queue})
        job_service.log(job, message, level=enums.LogLevel.ERROR)
        job.status = enums.JobStatus.FAILED
        job.error = message[:500]
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error", "finished_at", "updated_at"])
        return "unconsumed"

    job_service.log(job, f"Queued on {queue}", context_queue=queue)
    return "queued"


@shared_task(
    name="leadgen.tasks.run_ai_enrichment",
    queue="leadgen_bg",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=2,
)
def run_ai_enrichment(job_id: str) -> dict:
    """Enrich every lead on a job.

    Background queue by default: enrichment costs money per lead and nobody is
    waiting on it the way they wait on discovery, so it must never delay a
    search a rep is watching.
    """
    from leadgen.services import ai

    job = SearchJob.objects.filter(pk=job_id).first()
    if job is None:
        return {"job": job_id, "status": "missing"}

    completed = ai.enrich_job(job)
    job_service.log(
        job,
        f"AI enrichment finished — {completed} leads analysed",
        stage=enums.PipelineStage.SCORING,
    )
    return {"job": str(job.id), "enriched": completed}


@shared_task(
    name="leadgen.tasks.run_verification",
    queue="leadgen_bg",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=2,
)
def run_verification(job_id: str) -> dict:
    """Verify every contact on a job's leads, then re-score.

    Re-scoring is part of the same task rather than a follow-up: verification
    changes the fit score, and a queue that left scores stale until the next
    unrelated run would show a rep a number that contradicts the record.
    """
    from leadgen.services import pipeline, verification

    job = SearchJob.objects.filter(pk=job_id).first()
    if job is None:
        return {"job": job_id, "status": "missing"}

    completed = verification.verify_job(job)
    for lead in job.leads.filter(duplicate_of__isnull=True).iterator(chunk_size=100):
        pipeline.score(lead)

    job_service.log(job, f"Verification finished — {completed} contacts checked")
    return {"job": str(job.id), "verified": completed}


def enqueue_stage(job: SearchJob, task, label: str) -> str:
    """Queue a Phase 2 stage, running inline when no broker is reachable.

    Same contract as ``enqueue``: only a broker connection failure falls back,
    never a task error.
    """
    if consumers_for("leadgen_bg") == 0:
        message = (
            f"No Celery worker is consuming “leadgen_bg”, so {label} would wait "
            "forever. Start a worker with -Q leadgen_bg."
        )
        job_service.log(job, message, level=enums.LogLevel.ERROR)
        return "unconsumed"

    try:
        task.apply_async(args=[str(job.id)], queue="leadgen_bg")
    except OperationalError as exc:
        logger.error("leadgen.enqueue.no_broker", extra={"job": str(job.id), "error": str(exc)})
        job_service.log(
            job,
            f"No Celery broker reachable — running {label} synchronously",
            level=enums.LogLevel.WARNING,
        )
        task(str(job.id))
        return "inline"

    job_service.log(job, f"{label} queued")
    return "queued"
