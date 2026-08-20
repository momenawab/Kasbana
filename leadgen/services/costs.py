"""Cost and usage reporting, read from the ``ApiUsage`` ledger.

Every figure here is derived from rows written at call time, never estimated
from lead counts. A dashboard that multiplies leads by an assumed price looks
authoritative and drifts from the invoice the moment anything changes — a job
that split into more cells, a lead with three emails instead of one, a retry.

Prices themselves are estimates and are labelled as such: they come from
settings, not from the providers, so an out-of-date rate skews every figure in
the same direction. ``rates()`` exposes them so the UI can say so.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, DecimalField, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from leadgen import enums
from leadgen.models import ApiUsage, GeneratedLead

_ZERO = Decimal("0")


def _sum(queryset, field: str) -> Decimal:
    return queryset.aggregate(total=Coalesce(Sum(field), _ZERO, output_field=DecimalField()))[
        "total"
    ]


def summary(*, days: int = 30) -> dict:
    """Spend and volume over the last ``days``, plus cost per usable lead.

    Cost per lead divides by leads that survived deduplication, not by every row
    discovered: the duplicates were merged into their survivor, so counting them
    would understate the true cost of a lead a rep can actually call.
    """
    since = timezone.now() - timedelta(days=days)
    usage = ApiUsage.objects.filter(created_at__gte=since)

    total_cost = _sum(usage, "cost_usd")
    leads = GeneratedLead.objects.filter(created_at__gte=since, duplicate_of__isnull=True).count()
    imported = GeneratedLead.objects.filter(
        imported_at__gte=since, imported_lead__isnull=False
    ).count()

    return {
        "days": days,
        "total_cost_usd": total_cost,
        "total_calls": usage.aggregate(n=Coalesce(Sum("calls"), 0))["n"],
        "total_tokens_in": usage.aggregate(n=Coalesce(Sum("tokens_in"), 0))["n"],
        "total_tokens_out": usage.aggregate(n=Coalesce(Sum("tokens_out"), 0))["n"],
        "leads": leads,
        "imported": imported,
        "cost_per_lead_usd": (total_cost / leads) if leads else _ZERO,
        # The number that matters commercially: discovery is only worth its
        # price if the leads become CRM records somebody works.
        "cost_per_imported_usd": (total_cost / imported) if imported else None,
        "by_provider": by_provider(since),
        "daily": daily(since),
        "rates_are_estimates": True,
    }


def by_provider(since=None) -> list[dict]:
    usage = ApiUsage.objects.all()
    if since:
        usage = usage.filter(created_at__gte=since)

    rows = (
        usage.values("provider")
        .annotate(
            calls=Coalesce(Sum("calls"), 0),
            cost_usd=Coalesce(Sum("cost_usd"), _ZERO, output_field=DecimalField()),
            tokens_in=Coalesce(Sum("tokens_in"), 0),
            tokens_out=Coalesce(Sum("tokens_out"), 0),
            failures=Count("id", filter=Q(succeeded=False)),
        )
        .order_by("-cost_usd")
    )
    labels = dict(enums.ApiProvider.choices)
    return [{**row, "provider_label": labels.get(row["provider"], row["provider"])} for row in rows]


def daily(since=None) -> list[dict]:
    """Spend per day, for the cost chart."""
    usage = ApiUsage.objects.all()
    if since:
        usage = usage.filter(created_at__gte=since)

    return list(
        usage.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            cost_usd=Coalesce(Sum("cost_usd"), _ZERO, output_field=DecimalField()),
            calls=Coalesce(Sum("calls"), 0),
        )
        .order_by("day")
    )


def for_job(job) -> dict:
    """What one job cost. The figure an operator wants next to its results."""
    usage = ApiUsage.objects.filter(job=job)
    cost = _sum(usage, "cost_usd")
    usable = job.leads.filter(duplicate_of__isnull=True).count()
    return {
        "total_cost_usd": cost,
        "calls": usage.aggregate(n=Coalesce(Sum("calls"), 0))["n"],
        "cost_per_lead_usd": (cost / usable) if usable else _ZERO,
        "by_provider": list(
            usage.values("provider").annotate(
                cost_usd=Coalesce(Sum("cost_usd"), _ZERO, output_field=DecimalField()),
                calls=Coalesce(Sum("calls"), 0),
            )
        ),
    }


def rates() -> dict:
    """The configured prices, so the UI can show what the figures assume."""
    return {
        "glm_per_mtok_in": settings.GLM_PRICE_PER_MTOK_IN,
        "glm_per_mtok_out": settings.GLM_PRICE_PER_MTOK_OUT,
        "places_per_call": settings.PLACES_PRICE_PER_CALL_USD,
        "geocoding_per_call": settings.GEOCODING_PRICE_PER_CALL_USD,
        "twilio_lookup_per_call": settings.TWILIO_LOOKUP_PRICE_USD,
        "hunter_per_call": settings.HUNTER_PRICE_USD,
    }
