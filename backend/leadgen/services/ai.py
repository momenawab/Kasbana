"""AI enrichment — what a model can infer about a business we have not met.

The prompt is built only from what we actually observed: the Places listing and,
where there was one, the business's own website. Nothing is invented for it and
nothing is implied to the model that we did not see, because a model given a
confident-sounding blank will confidently fill it.

Everything that comes back is treated as an **estimate**, coerced to the right
type, and clamped to a sane range before it touches the database. A model that
returns 8 million daily visitors for a Maadi cafe must not put that number in
front of a rep, and a string where an integer belongs must not become a silent
zero. The raw response is kept alongside so a wrong-looking field can be traced
to a bad answer rather than a bad parse.

Deliberately absent from the output schema: anything about a named individual.
The model is not asked to guess who owns a business — that comes from what the
business publishes about itself (``leadgen.owner``) or from a rep asking, and a
plausible invented name is the most dangerous output this pipeline could produce.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from leadgen import enums
from leadgen.glm import PROMPT_VERSION, GlmClient, GlmError, GlmNotConfigured
from leadgen.models import AiEnrichment, ApiUsage, GeneratedLead

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You analyse small businesses for a loyalty-programme sales team in Egypt.

You will be given only what was observed on a Google Places listing and, when the
business has one, its own website. Base every answer on that evidence.

Rules:
- Return a single JSON object and nothing else. No prose, no code fence.
- Every numeric answer is an estimate. If the evidence does not support one,
  use null rather than guessing a plausible number.
- Never name a person. Do not guess owners, managers or staff.
- Keep `business_summary` to two sentences and `recommended_pitch` to one.
- Likelihood fields are integers 0-100.
"""

# The shape the model must answer in. Sent verbatim so the contract the parser
# enforces and the contract the model is given cannot drift apart.
OUTPUT_SCHEMA = """{
  "business_summary": string,
  "target_customers": string,
  "estimated_size": "micro" | "small" | "medium" | "large",
  "estimated_daily_visitors": integer | null,
  "estimated_monthly_customers": integer | null,
  "estimated_revenue_range": string | null,
  "business_model": "independent" | "chain" | "franchise",
  "is_franchise": boolean,
  "is_premium": boolean,
  "estimated_branches": integer | null,
  "likelihood_uses_pos": integer,
  "likelihood_uses_loyalty": integer,
  "likelihood_accepts_digital": integer,
  "recommended_pitch": string,
  "recommended_plan": "starter" | "growth" | "chain" | "enterprise",
  "risk_level": "low" | "medium" | "high",
  "confidence": integer
}"""

# Clamps. Chosen to be generous enough never to distort a real answer and tight
# enough to catch a hallucinated order of magnitude.
MAX_DAILY_VISITORS = 20_000
MAX_MONTHLY_CUSTOMERS = 600_000
MAX_BRANCHES = 500

_SIZES = {"micro", "small", "medium", "large"}
_MODELS = {"independent", "chain", "franchise"}
_PLANS = {"starter", "growth", "chain", "enterprise"}


def build_user_prompt(lead: GeneratedLead) -> str:
    """Assemble the evidence. Absent facts are stated as absent, not omitted.

    Saying "no website found" is materially different from saying nothing about
    a website: the first is evidence about a business's digital maturity, the
    second invites the model to assume one exists.
    """
    profile = getattr(lead, "website_profile", None)
    socials = [social.platform for social in lead.socials.all()]

    lines = [
        f"Business name: {lead.business_name}",
        f"Category: {lead.category_display or 'unknown'}",
        f"Address: {lead.address or 'unknown'}",
        f"Google rating: {lead.rating if lead.rating is not None else 'not yet rated'}",
        f"Google review count: {lead.reviews_count}",
        f"Photos on listing: {lead.photos_count}",
        f"Listing status: {lead.business_status or 'unknown'}",
        f"Distinct locations found under this name: {lead.branch_count}",
        f"Phone on listing: {'yes' if lead.phone_e164 else 'no'}",
    ]

    if lead.opening_hours.get("weekdayDescriptions"):
        lines.append("Opening hours: " + "; ".join(lead.opening_hours["weekdayDescriptions"]))

    lines.append(f"Social profiles linked: {', '.join(socials) if socials else 'none found'}")

    if not lead.website_domain:
        lines.append(
            "Website: none of its own"
            + (" (the listed link is a social or marketplace page)" if lead.website else "")
        )
    elif profile is None:
        lines.append(f"Website: {lead.website_domain} (not crawled)")
    else:
        lines.append(f"Website: {lead.website_domain}")
        if profile.meta_description:
            lines.append(f"Site description: {profile.meta_description}")
        if profile.about_text:
            lines.append(f"About page extract: {profile.about_text[:800]}")
        if profile.legal_entity:
            lines.append(f"Operating company named on the site: {profile.legal_entity}")
        lines.append(f"Emails published: {len(profile.emails)}")
        for label, values in (
            ("POS software detected", profile.pos_vendors),
            ("Loyalty software detected", profile.loyalty_vendors),
            ("Payment providers detected", profile.payment_providers),
            ("Delivery platforms detected", profile.delivery_platforms),
            ("Reservation platforms detected", profile.reservation_platforms),
        ):
            lines.append(f"{label}: {', '.join(values) if values else 'none'}")

    return (
        "\n".join(lines)
        + "\n\nAnalyse this business and answer with exactly this JSON shape:\n"
        + OUTPUT_SCHEMA
    )


# ── Coercion ─────────────────────────────────────────────────────────────────
def _int_or_none(value, *, maximum: int) -> int | None:
    """An integer within range, or None. Never a silent zero.

    A model that answers "about 300" or 300.0 meant 300; one that answers
    "lots" meant nothing, and None says so honestly. Zero would read as a
    measured finding of none.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return min(number, maximum)


def _percent(value) -> int | None:
    number = _int_or_none(value, maximum=100)
    return number


def _bool_or_none(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes"}:
            return True
        if lowered in {"false", "no"}:
            return False
    return None


def _choice(value, allowed: set[str]) -> str:
    if not isinstance(value, str):
        return ""
    lowered = value.strip().lower()
    return lowered if lowered in allowed else ""


def _text(value, limit: int) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def parse_analysis(data: dict) -> dict:
    """Coerce a model response into the fields ``AiEnrichment`` stores.

    Total rather than partial: an unparseable field becomes null and the row
    still saves. A single bad field should not discard an otherwise useful
    analysis we have already paid for.
    """
    return {
        "business_summary": _text(data.get("business_summary"), 2000),
        "target_customers": _text(data.get("target_customers"), 500),
        "estimated_size": _choice(data.get("estimated_size"), _SIZES),
        "estimated_daily_visitors": _int_or_none(
            data.get("estimated_daily_visitors"), maximum=MAX_DAILY_VISITORS
        ),
        "estimated_monthly_customers": _int_or_none(
            data.get("estimated_monthly_customers"), maximum=MAX_MONTHLY_CUSTOMERS
        ),
        "estimated_revenue_range": _text(data.get("estimated_revenue_range"), 120),
        "business_model": _choice(data.get("business_model"), _MODELS),
        "is_franchise": _bool_or_none(data.get("is_franchise")),
        "is_premium": _bool_or_none(data.get("is_premium")),
        "estimated_branches": _int_or_none(data.get("estimated_branches"), maximum=MAX_BRANCHES),
        "likelihood_uses_pos": _percent(data.get("likelihood_uses_pos")),
        "likelihood_uses_loyalty": _percent(data.get("likelihood_uses_loyalty")),
        "likelihood_accepts_digital": _percent(data.get("likelihood_accepts_digital")),
        "recommended_pitch": _text(data.get("recommended_pitch"), 2000),
        "recommended_plan": _choice(data.get("recommended_plan"), _PLANS),
        "risk_level": _choice(data.get("risk_level"), set(enums.RiskLevel.values)),
        "confidence": _percent(data.get("confidence")),
    }


# ── The stage ────────────────────────────────────────────────────────────────
def enrich(lead: GeneratedLead, *, client: GlmClient | None = None) -> AiEnrichment:
    """Run AI enrichment for one lead. Never raises — failure is recorded.

    A model outage must not fail a job: the lead keeps its observed signals and
    its fit score, and the queue shows what went wrong so it can be retried.
    """
    record, _ = AiEnrichment.objects.get_or_create(lead=lead)
    record.status = enums.TaskStatus.RUNNING
    record.attempts += 1
    record.error = ""
    record.save(update_fields=["status", "attempts", "error", "updated_at"])

    # Nothing useful to say about a business Google reports as gone, and no
    # reason to pay a model to say it.
    if lead.business_status == "CLOSED_PERMANENTLY":
        record.status = enums.TaskStatus.SKIPPED
        record.error = "Business is permanently closed."
        record.save(update_fields=["status", "error", "updated_at"])
        return record

    client = client or GlmClient()

    try:
        result = client.complete_json(system=SYSTEM_PROMPT, user=build_user_prompt(lead))
    except (GlmError, GlmNotConfigured) as exc:
        logger.warning("leadgen.ai.failed", extra={"lead": str(lead.id), "error": str(exc)})
        record.status = enums.TaskStatus.FAILED
        record.error = str(exc)[:500]
        record.save(update_fields=["status", "error", "updated_at"])
        # A failed call still consumed quota at the provider more often than
        # not, so it is recorded — under-counting spend is the worse error.
        _record_usage(lead, tokens_in=0, tokens_out=0, cost=Decimal("0"), succeeded=False)
        return record

    for field_name, value in parse_analysis(result.data).items():
        setattr(record, field_name, value)

    record.status = enums.TaskStatus.COMPLETED
    record.model = result.model
    record.prompt_version = PROMPT_VERSION
    record.tokens_in = result.tokens_in
    record.tokens_out = result.tokens_out
    record.cost_usd = result.cost_usd
    record.duration_ms = result.duration_ms
    record.raw_response = result.raw
    record.save()

    _record_usage(
        lead,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost=result.cost_usd,
        succeeded=True,
    )
    return record


def _record_usage(
    lead: GeneratedLead, *, tokens_in: int, tokens_out: int, cost: Decimal, succeeded: bool
) -> None:
    ApiUsage.objects.create(
        provider=enums.ApiProvider.GLM,
        operation="chat.completions",
        job=lead.job,
        lead=lead,
        calls=1,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        succeeded=succeeded,
    )


def enrich_job(job, *, client: GlmClient | None = None) -> int:
    """Enrich every ready lead on a job. Returns how many completed.

    Sequential on purpose. Concurrency here would multiply spend against a rate
    limit we do not control, and the stage is not latency-critical — nobody is
    waiting on it the way they wait on discovery.
    """
    client = client or GlmClient()
    leads = job.leads.filter(duplicate_of__isnull=True).select_related("website_profile")

    completed = 0
    for lead in leads.iterator(chunk_size=50):
        record = enrich(lead, client=client)
        if record.status == enums.TaskStatus.COMPLETED:
            completed += 1
    return completed
