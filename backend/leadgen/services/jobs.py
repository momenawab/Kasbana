"""Search-job lifecycle and orchestration.

The rules that must hold no matter who starts a job — the API, a retry, or a
test — live here rather than in a view or a Celery task, so a job means the
same thing however it was launched.

Cancellation and pausing are cooperative: the worker re-reads the job's status
between leads and stops when it changes. There is no way to interrupt a task
mid-HTTP-call, and pretending otherwise would mean a "cancelled" job that keeps
spending Places quota for another minute. Between-lead granularity is honest
and bounded.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from decimal import Decimal

from leadgen import enums
from leadgen.models import ApiUsage, GeneratedLead, JobLog, SearchJob
from leadgen.places import PlacesClient, PlacesError
from leadgen.services import discovery, pipeline

logger = logging.getLogger(__name__)


class JobError(RuntimeError):
    """A job cannot proceed. Message is operator-facing."""


# ── Logging ──────────────────────────────────────────────────────────────────
def log(
    job: SearchJob,
    message: str,
    *,
    stage: str = "",
    level: str = enums.LogLevel.INFO,
    lead: GeneratedLead | None = None,
    **context,
) -> JobLog:
    """Append one line to the job's operator log.

    Separate from ``AdminAuditLog`` (which answers "who did what" for
    compliance): most entries here have no human actor, and the question is
    "what did the pipeline do and why did it stall".
    """
    return JobLog.objects.create(
        job=job,
        lead=lead,
        stage=stage,
        level=level,
        message=message[:500],
        context=context or {},
    )


# ── Creation ─────────────────────────────────────────────────────────────────
def create(
    *,
    country: str,
    city: str,
    business_types: list[str],
    province: str = "",
    street: str = "",
    radius_km: int = 5,
    max_results: int = 100,
    priority: str = enums.JobPriority.NORMAL,
    created_by=None,
    client: PlacesClient | None = None,
) -> SearchJob:
    """Create a job and geocode its centre.

    Geocoding happens now, not at run time, because an unplaceable address is a
    correction the operator should get while they are still looking at the form
    — not a failure discovered by a worker ten minutes later.
    """
    if not business_types:
        raise JobError("Select at least one business type.")
    if max_results not in enums.ALLOWED_MAX_RESULTS:
        raise JobError(f"Max results must be one of {enums.ALLOWED_MAX_RESULTS}.")

    unknown = set(business_types) - set(enums.BusinessType.values)
    if unknown:
        raise JobError(f"Unknown business types: {', '.join(sorted(unknown))}")

    job = SearchJob(
        country=country.upper()[:2],
        province=province,
        city=city,
        street=street,
        radius_km=radius_km,
        business_types=list(dict.fromkeys(business_types)),  # de-duped, order kept
        max_results=max_results,
        priority=priority,
        created_by=created_by,
    )

    address = ", ".join(part for part in (street, city, province, country) if part)
    try:
        located = (client or PlacesClient()).geocode(address, region=country)
    except PlacesError as exc:
        raise JobError(f"Could not geocode “{address}”: {exc}") from exc

    if located is None:
        raise JobError(f"Google could not place “{address}”. Check the city and street.")

    job.center_lat, job.center_lng = located
    job.save()
    ApiUsage.objects.create(
        provider=enums.ApiProvider.GOOGLE_GEOCODING,
        operation="geocode",
        job=job,
        calls=1,
        cost_usd=Decimal(str(settings.GEOCODING_PRICE_PER_CALL_USD)),
    )
    log(job, f"Job created for {address}", stage=enums.PipelineStage.DISCOVERY)
    return job


# ── Transitions ──────────────────────────────────────────────────────────────
def _transition(job: SearchJob, status: str, **fields) -> SearchJob:
    job.status = status
    for key, value in fields.items():
        setattr(job, key, value)
    job.save(update_fields=["status", *fields.keys(), "updated_at"])
    return job


def pause(job: SearchJob) -> SearchJob:
    if job.status != enums.JobStatus.RUNNING:
        raise JobError("Only a running job can be paused.")
    log(job, "Paused by operator")
    return _transition(job, enums.JobStatus.PAUSED)


def resume(job: SearchJob) -> SearchJob:
    if job.status != enums.JobStatus.PAUSED:
        raise JobError("Only a paused job can be resumed.")
    log(job, "Resumed by operator")
    return _transition(job, enums.JobStatus.QUEUED)


def cancel(job: SearchJob) -> SearchJob:
    if job.is_terminal:
        raise JobError("This job has already finished.")
    log(job, "Cancelled by operator")
    return _transition(job, enums.JobStatus.CANCELLED, finished_at=timezone.now())


def retry(job: SearchJob) -> SearchJob:
    """Re-queue a finished job, discarding its previous results.

    A retry starts clean rather than resuming: the usual reason to retry is a
    misconfiguration or an outage, and leads found under the broken condition
    should not be blended with leads found after it was fixed.
    """
    if not job.is_terminal:
        raise JobError("Only a finished job can be retried.")

    with transaction.atomic():
        job.leads.all().delete()
        _transition(
            job,
            enums.JobStatus.QUEUED,
            discovered_count=0,
            duplicate_count=0,
            crawled_count=0,
            ready_count=0,
            imported_count=0,
            failed_count=0,
            started_at=None,
            finished_at=None,
            error="",
            stage="",
        )
    log(job, "Retry requested — previous results discarded")
    return job


def _record_places_usage(job: SearchJob, calls: int) -> None:
    """Bill the job for the Places calls discovery actually made."""
    if calls <= 0:
        return
    ApiUsage.objects.create(
        provider=enums.ApiProvider.GOOGLE_PLACES,
        operation="places.searchText",
        job=job,
        calls=calls,
        cost_usd=Decimal(str(settings.PLACES_PRICE_PER_CALL_USD)) * calls,
    )


def _should_stop(job: SearchJob) -> bool:
    """Whether the operator has paused or cancelled since the last check."""
    status = SearchJob.objects.filter(pk=job.pk).values_list("status", flat=True).first()
    return status in (enums.JobStatus.PAUSED, enums.JobStatus.CANCELLED)


# ── Execution ────────────────────────────────────────────────────────────────
def run(job: SearchJob, *, client: PlacesClient | None = None) -> SearchJob:
    """Run the whole pipeline for ``job``.

    Called by the Celery task in production and directly in tests. Every stage
    is re-runnable, so a job interrupted between stages can be re-run without
    duplicating work.
    """
    if job.status not in (enums.JobStatus.QUEUED, enums.JobStatus.RUNNING):
        raise JobError(f"A {job.status} job cannot be run.")

    client = client or PlacesClient()
    _transition(job, enums.JobStatus.RUNNING, started_at=job.started_at or timezone.now())

    try:
        _run_discovery(job, client)
        if _halted(job):
            return job

        _run_dedupe(job)
        if _halted(job):
            return job

        _run_enrichment(job)
        if _halted(job):
            return job

        _finish(job)
    except Exception as exc:  # noqa: BLE001 — the job must record why it died
        logger.exception("leadgen.job.failed", extra={"job": str(job.id)})
        log(job, f"Job failed: {exc}", level=enums.LogLevel.ERROR, stage=job.stage)
        _transition(
            job,
            enums.JobStatus.FAILED,
            error=str(exc)[:500],
            finished_at=timezone.now(),
        )

    job.refresh_from_db()
    return job


def _halted(job: SearchJob) -> bool:
    if not _should_stop(job):
        return False
    job.refresh_from_db()
    log(job, f"Stopped after {job.stage or 'discovery'} — job is {job.status}")
    return True


def _run_discovery(job: SearchJob, client: PlacesClient) -> None:
    _transition(job, enums.JobStatus.RUNNING, stage=enums.PipelineStage.DISCOVERY)
    log(job, "Discovery started", stage=enums.PipelineStage.DISCOVERY)

    before = client.billed_calls
    created = discovery.discover(job, client)

    # The ledger is written from the client's own call counter, not from the
    # number of leads produced: a cell that returned nothing still cost a call,
    # and pricing by results would understate every sparse search.
    _record_places_usage(job, client.billed_calls - before)

    job.discovered_count = job.leads.count()
    job.save(update_fields=["discovered_count", "updated_at"])
    log(
        job,
        f"Discovery found {created} businesses in {client.billed_calls} billed calls",
        stage=enums.PipelineStage.DISCOVERY,
        billed_calls=client.billed_calls,
    )


def _run_dedupe(job: SearchJob) -> None:
    _transition(job, enums.JobStatus.RUNNING, stage=enums.PipelineStage.DEDUPLICATION)
    marked = pipeline.deduplicate(job)
    log(
        job,
        f"Deduplication collapsed {marked} listings",
        stage=enums.PipelineStage.DEDUPLICATION,
    )


def _run_enrichment(job: SearchJob) -> None:
    """Crawl, resolve owners, score and CRM-match every surviving lead.

    Progress is committed per lead so a long job reports honestly while it runs
    and keeps everything it finished if it is cancelled halfway.
    """
    _transition(job, enums.JobStatus.RUNNING, stage=enums.PipelineStage.WEBSITE_CRAWL)
    leads = job.leads.filter(duplicate_of__isnull=True).order_by("-reviews_count")

    crawled = ready = failed = 0

    for lead in leads.iterator(chunk_size=100):
        if _should_stop(job):
            break
        try:
            pipeline.enrich(lead)
            crawled += 1

            lead.refresh_from_db()
            pipeline.score(lead)
            pipeline.match_crm(lead)

            lead.refresh_from_db()
            if lead.state == enums.LeadState.READY:
                ready += 1
        except Exception as exc:  # noqa: BLE001 — one bad site is not a job failure
            failed += 1
            logger.warning(
                "leadgen.enrich.failed", extra={"lead": str(lead.id), "error": str(exc)}
            )
            log(
                job,
                f"{lead.business_name}: enrichment failed — {exc}",
                stage=enums.PipelineStage.WEBSITE_CRAWL,
                level=enums.LogLevel.WARNING,
                lead=lead,
            )
            GeneratedLead.objects.filter(pk=lead.pk).update(state=enums.LeadState.FAILED)

        if (crawled + failed) % 25 == 0:
            _save_counters(job, crawled, ready, failed)

    _save_counters(job, crawled, ready, failed)
    log(
        job,
        f"Enrichment complete — {ready} ready, {failed} failed",
        stage=enums.PipelineStage.SCORING,
    )


def _save_counters(job: SearchJob, crawled: int, ready: int, failed: int) -> None:
    job.crawled_count = crawled
    job.ready_count = ready
    job.failed_count = failed
    job.save(update_fields=["crawled_count", "ready_count", "failed_count", "updated_at"])


def _finish(job: SearchJob) -> None:
    _transition(
        job,
        enums.JobStatus.COMPLETED,
        stage=enums.PipelineStage.CRM_MATCH,
        finished_at=timezone.now(),
    )
    log(
        job,
        f"Job complete — {job.ready_count} leads ready for CRM",
        stage=enums.PipelineStage.CRM_MATCH,
    )
