"""Dashboard metrics and chart series.

Every figure is computed from the tables rather than from a maintained counter,
because a dashboard that drifts from the data is worse than no dashboard — it
gets believed. The queries are cheap: each is a single indexed aggregate, and
the whole dashboard is a handful of round trips.

Two of the spec's charts needed reinterpreting, and both are noted where they
are built: "Sources" and "Conversion Rate" mean something specific here that
they do not mean in the CRM.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from leadgen import enums, scoring
from leadgen.models import ApiUsage, GeneratedLead, SearchJob, Verification

_ZERO = Decimal("0")


def _usable():
    """Leads a rep could actually call: survivors of deduplication.

    Every count on the dashboard uses this. Including merged branches would
    inflate the funnel and make a chain of five look like five opportunities.
    """
    return GeneratedLead.objects.filter(duplicate_of__isnull=True)


def metrics() -> dict:
    """The header cards."""
    now = timezone.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    usable = _usable()

    verified_lead_ids = Verification.objects.filter(
        kind=enums.VerificationKind.PHONE, result=enums.VerificationResult.VERIFIED
    ).values("lead_id")

    usage = ApiUsage.objects.all()

    return {
        "total_leads": usable.count(),
        "new_today": usable.filter(created_at__gte=today).count(),
        # "Verified" means a provider confirmed the phone — not that the offline
        # fallback found it plausible. See leadgen.verify for why those differ.
        "verified": usable.filter(id__in=verified_lead_ids).count(),
        "pending": usable.filter(
            state__in=[enums.LeadState.DISCOVERED, enums.LeadState.ENRICHING]
        ).count(),
        "ready": usable.filter(state=enums.LeadState.READY).count(),
        "rejected": usable.filter(state=enums.LeadState.REJECTED).count(),
        "hot_leads": usable.filter(score_label=enums.ScoreLabel.HOT).count(),
        "average_score": round(
            usable.aggregate(avg=Coalesce(Avg("fit_score"), 0.0))["avg"] or 0, 1
        ),
        "imported": usable.filter(imported_lead__isnull=False).count(),
        "jobs_running": SearchJob.objects.filter(
            status__in=[enums.JobStatus.RUNNING, enums.JobStatus.QUEUED]
        ).count(),
        "jobs_failed": SearchJob.objects.filter(status=enums.JobStatus.FAILED).count(),
        # Named "estimated" throughout: they rest on configured prices, not on
        # provider invoices, and the UI repeats the caveat.
        "estimated_cost_usd": usage.aggregate(
            total=Coalesce(Sum("cost_usd"), _ZERO, output_field=DecimalField())
        )["total"],
        "estimated_tokens": usage.aggregate(
            n=Coalesce(Sum("tokens_in"), 0) + Coalesce(Sum("tokens_out"), 0)
        )["n"],
        "estimated_api_calls": usage.aggregate(n=Coalesce(Sum("calls"), 0))["n"],
    }


def leads_per_day(days: int = 30) -> list[dict]:
    since = timezone.now() - timedelta(days=days)
    return list(
        _usable()
        .filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )


def leads_by_city(limit: int = 10) -> list[dict]:
    """Grouped by the job's city, not the lead's address.

    A job splits into sub-cells across districts, so parsing each address would
    scatter one search across a dozen labels. The city a search was aimed at is
    the unit an operator actually thinks in.
    """
    return list(
        _usable()
        .values(city=F("job__city"))
        .annotate(count=Count("id"))
        .order_by("-count")[:limit]
    )


def score_distribution() -> list[dict]:
    """Counts per ten-point band, so the shape of the funnel is visible.

    Bands rather than the four labels: the labels are already a card, and the
    thing worth seeing here is whether scores cluster somewhere the thresholds
    cut awkwardly — which is exactly how the Phase 1 weighting problem showed up.
    """
    buckets = {f"{low}-{low + 9}": 0 for low in range(0, 100, 10)}
    rows = (
        _usable()
        .values_list("fit_score", flat=True)
    )
    for value in rows:
        low = min(int(value) // 10 * 10, 90)
        buckets[f"{low}-{low + 9}"] += 1
    return [{"band": band, "count": count} for band, count in buckets.items()]


def by_label() -> list[dict]:
    labels = dict(enums.ScoreLabel.choices)
    rows = (
        _usable().values("score_label").annotate(count=Count("id")).order_by("-count")
    )
    return [
        {"label": row["score_label"] or "unscored",
         "label_display": labels.get(row["score_label"], "Unscored"),
         "count": row["count"]}
        for row in rows
    ]


def conversion_funnel() -> dict:
    """Discovered → ready → imported → converted to a paying merchant.

    Not the CRM's conversion rate. This measures whether *prospecting* is worth
    its cost: leads that reached the CRM, and of those, how many became
    merchants. The last step reads through to console.Lead.converted_merchant,
    which is the only place that truth lives.
    """
    usable = _usable()
    discovered = usable.count()
    ready = usable.filter(
        state__in=[enums.LeadState.READY, enums.LeadState.IMPORTED]
    ).count()
    imported = usable.filter(imported_lead__isnull=False).count()
    converted = usable.filter(imported_lead__converted_merchant__isnull=False).count()

    def rate(part: int, whole: int) -> float:
        return round(part / whole * 100, 1) if whole else 0.0

    return {
        "discovered": discovered,
        "ready": ready,
        "imported": imported,
        "converted": converted,
        "ready_rate": rate(ready, discovered),
        "import_rate": rate(imported, ready),
        "conversion_rate": rate(converted, imported),
    }


def owner_sources() -> list[dict]:
    """Where owner names came from — the spec's "Sources" chart, reinterpreted.

    Discovery source would be a single bar reading "Google Places" for every
    lead, since that is the only source this module has. Owner provenance is the
    one source dimension here that varies and that anyone acts on: it shows how
    much of the pipeline has a name at all, and how much of that came from a rep
    asking rather than from a page.
    """
    sources = dict(enums.OwnerNameSource.choices)
    rows = (
        _usable().values("owner_name_source").annotate(count=Count("id")).order_by("-count")
    )
    return [
        {
            "source": row["owner_name_source"] or "none",
            "source_display": sources.get(row["owner_name_source"], "No owner found"),
            "count": row["count"],
        }
        for row in rows
    ]


def by_category(limit: int = 12) -> list[dict]:
    labels = dict(enums.BusinessType.choices)
    rows = (
        _usable()
        .exclude(category="")
        .values("category")
        .annotate(count=Count("id"), avg_score=Coalesce(Avg("fit_score"), 0.0))
        .order_by("-count")[:limit]
    )
    return [
        {
            "category": row["category"],
            "category_display": labels.get(row["category"], row["category"]),
            "count": row["count"],
            "avg_score": round(row["avg_score"], 1),
        }
        for row in rows
    ]


def web_presence() -> dict:
    """How much of the market is reachable online at all.

    Not in the spec, and included because the live Maadi run made it the single
    most decision-relevant number here: two thirds of Egyptian F&B had no site
    of their own, which is what forced the scoring rebalance. Anyone tuning
    weights later needs to see this before they start.
    """
    usable = _usable()
    total = usable.count()
    return {
        "total": total,
        "with_website": usable.exclude(website_domain="").count(),
        "with_social_only": usable.filter(website_domain="").exclude(website="").count(),
        "with_nothing": usable.filter(website_domain="", website="").count(),
        "with_owner_name": usable.exclude(owner_name="").count(),
    }


def dashboard(days: int = 30) -> dict:
    """Everything the dashboard screen needs, in one response."""
    return {
        "metrics": metrics(),
        "leads_per_day": leads_per_day(days),
        "leads_by_city": leads_by_city(),
        "score_distribution": score_distribution(),
        "by_label": by_label(),
        "conversion": conversion_funnel(),
        "owner_sources": owner_sources(),
        "by_category": by_category(),
        "web_presence": web_presence(),
    }
