"""The verification stage — running phone and email checks and recording them.

Targets come from what discovery and the crawl actually found: the listing's
phone and any addresses published on the business's own site. Nothing is
constructed. Guessing ``firstname@domain`` and verifying the guess would put an
address in front of a rep that the business never published, and a bounce from
it is a worse first impression than no email at all.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from leadgen import enums, verify
from leadgen.models import ApiUsage, GeneratedLead, Verification

logger = logging.getLogger(__name__)

# Verifying every address on a contact page costs a credit each and tells a rep
# little more than the first few do.
MAX_EMAILS_PER_LEAD = 3


def targets_for(lead: GeneratedLead) -> list[tuple[str, str]]:
    """The (kind, target) pairs worth checking for one lead."""
    targets: list[tuple[str, str]] = []

    if lead.phone_e164:
        targets.append((enums.VerificationKind.PHONE, lead.phone_e164))

    profile = getattr(lead, "website_profile", None)
    for email in (profile.emails if profile else [])[:MAX_EMAILS_PER_LEAD]:
        targets.append((enums.VerificationKind.EMAIL, email.lower()))

    return targets


def verify_lead(lead: GeneratedLead) -> list[Verification]:
    """Verify every contact on ``lead``. Never raises.

    Returns one row per target, updated in place on a re-run so a retried queue
    does not multiply its own backlog.
    """
    records: list[Verification] = []
    for kind, target in targets_for(lead):
        records.append(verify_target(lead, kind, target))
    return records


def verify_target(lead: GeneratedLead, kind: str, target: str) -> Verification:
    record, _ = Verification.objects.get_or_create(lead=lead, kind=kind, target=target[:254])
    record.status = enums.TaskStatus.RUNNING
    record.attempts += 1
    record.error = ""
    record.save(update_fields=["status", "attempts", "error", "updated_at"])

    try:
        if kind == enums.VerificationKind.PHONE:
            outcome = verify.verify_phone(target, region=lead.job.country)
        else:
            outcome = verify.verify_email(target)
    except Exception as exc:  # noqa: BLE001 — one bad contact is not a job failure
        logger.warning("leadgen.verify.failed", extra={"lead": str(lead.id), "error": str(exc)})
        record.status = enums.TaskStatus.FAILED
        record.error = str(exc)[:500]
        record.save(update_fields=["status", "error", "updated_at"])
        return record

    record.status = enums.TaskStatus.COMPLETED
    record.result = outcome.result
    record.provider = outcome.provider
    record.line_type = outcome.line_type
    record.carrier = outcome.carrier_name
    record.deliverable = outcome.deliverable
    record.is_disposable = outcome.is_disposable
    record.is_role_address = outcome.is_role_address
    record.domain_valid = outcome.domain_valid
    record.confidence = outcome.confidence
    record.credits_used = outcome.credits_used
    record.error = outcome.error[:500]
    record.raw_response = outcome.raw
    record.save()

    # Only a real provider call is billable. The offline fallback costs nothing
    # and must not appear in the ledger as spend that never happened.
    if outcome.provider and outcome.credits_used:
        ApiUsage.objects.create(
            provider=outcome.provider,
            operation=f"verify.{kind}",
            job=lead.job,
            lead=lead,
            calls=1,
            cost_usd=outcome.cost_usd or Decimal("0"),
            succeeded=outcome.result != enums.VerificationResult.UNKNOWN,
        )

    return record


def verify_job(job) -> int:
    """Verify every surviving lead on a job. Returns rows completed."""
    leads = job.leads.filter(duplicate_of__isnull=True).select_related("website_profile", "job")
    completed = 0
    for lead in leads.iterator(chunk_size=50):
        for record in verify_lead(lead):
            if record.status == enums.TaskStatus.COMPLETED:
                completed += 1
    return completed


def apply_to_score(lead: GeneratedLead) -> None:
    """Fold verification findings into the fit score.

    Re-scoring is idempotent (``leadgen.scoring`` derives from scratch), so this
    is safe to call after any verification run.
    """
    from leadgen.services import pipeline

    pipeline.score(lead)
