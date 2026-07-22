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


def enqueue(job: SearchJob) -> str:
    """Queue ``job``, or run it inline when no broker is reachable.

    Returns "queued" or "inline" so the caller can tell the operator which
    happened — a job that ran inline has already finished by the time the API
    responds, and the UI should not sit waiting for progress that will never
    arrive.
    """
    queue = QUEUE_FOR_PRIORITY.get(job.priority, "leadgen")

    try:
        run_search_job.apply_async(args=[str(job.id)], queue=queue)
    except OperationalError as exc:
        # No broker. Expected on a developer machine; alarming in production,
        # hence the error-level log either way.
        logger.error(
            "leadgen.enqueue.no_broker", extra={"job": str(job.id), "error": str(exc)}
        )
        job_service.log(
            job,
            "No Celery broker reachable — running synchronously",
            level=enums.LogLevel.WARNING,
        )
        job_service.run(job)
        return "inline"

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
        job, f"AI enrichment finished — {completed} leads analysed",
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
    try:
        task.apply_async(args=[str(job.id)], queue="leadgen_bg")
    except OperationalError as exc:
        logger.error(
            "leadgen.enqueue.no_broker", extra={"job": str(job.id), "error": str(exc)}
        )
        job_service.log(
            job,
            f"No Celery broker reachable — running {label} synchronously",
            level=enums.LogLevel.WARNING,
        )
        task(str(job.id))
        return "inline"

    job_service.log(job, f"{label} queued")
    return "queued"
