"""Read-only analytics aggregations for the dashboard (Phase 1.6).

All functions accept the caller's ``merchant`` and an optional date range
(``from_date`` / ``to_date`` as ``date`` objects). They return plain dicts/lists
suitable for the contract response shapes.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Count, Min
from django.db.models.functions import TruncDate
from django.utils import timezone

from core.enums import CustomerCardStatus, LedgerEvent, WalletPlatform
from core.models import (
    CustomerCard,
    Location,
    Merchant,
    Redemption,
    StampLedger,
    WalletRegistration,
)

DEFAULT_RANGE_DAYS = 30


def _date_range(from_date: date | None, to_date: date | None) -> tuple[date, date]:
    """Resolve optional date range; defaults to the last 30 days."""
    today = timezone.localdate()
    if to_date is None:
        to_date = today
    if from_date is None:
        from_date = today - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    return from_date, to_date


def _ledger_qs(merchant: Merchant, from_date: date, to_date: date):
    """Tenant + date scoped StampLedger queryset."""
    return StampLedger.objects.for_merchant(merchant).filter(
        created_at__date__gte=from_date, created_at__date__lte=to_date
    )


def timeseries(
    merchant: Merchant,
    metric: str,
    from_date: date | None = None,
    to_date: date | None = None,
    location_id: str | None = None,
) -> list[dict[str, Any]]:
    """Date-bucketed series for ``joins`` / ``stamps`` / ``redemptions``."""
    from_date, to_date = _date_range(from_date, to_date)

    qs = _ledger_qs(merchant, from_date, to_date)
    if location_id:
        qs = qs.filter(location_id=location_id)

    if metric == "joins":
        qs = qs.filter(event_type=LedgerEvent.ENROLL)
    elif metric == "stamps":
        qs = qs.filter(event_type=LedgerEvent.STAMP)
    elif metric == "redemptions":
        qs = qs.filter(event_type=LedgerEvent.REDEEM)
    else:
        raise ValueError(f"Unknown metric: {metric!r}")

    buckets = {
        row["date"]: row["value"]
        for row in qs.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(value=Count("id"))
        .order_by("date")
    }

    points: list[dict[str, Any]] = []
    cursor = from_date
    while cursor <= to_date:
        points.append({"date": cursor.isoformat(), "value": buckets.get(cursor, 0)})
        cursor += timedelta(days=1)
    return points


def summary(
    merchant: Merchant,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict[str, Any]:
    """Headline KPIs for one window — what happened between the two dates.

    Every figure counts ledger events inside the range, so the enrollments and
    redemptions tiles agree exactly with the charts below them, which read the same
    events. Two definitions only make sense windowed, and differ from the all-time
    view the Overview page asks for (``AnalyticsSummaryView`` with no range):

    - ``active_cards`` = cards that saw *any* event in the window, not a live total
      of every active card.
    - ``repeat_rate`` = of those, the share stamped more than once in the window.
    """
    from_date, to_date = _date_range(from_date, to_date)
    events = _ledger_qs(merchant, from_date, to_date)

    active_cards = events.values("customer_card_id").distinct().count()
    returning = (
        events.filter(event_type=LedgerEvent.STAMP)
        .values("customer_card_id")
        .annotate(stamps=Count("id"))
        .filter(stamps__gte=2)
        .count()
    )

    return {
        "enrollments": events.filter(event_type=LedgerEvent.ENROLL).count(),
        "active_cards": active_cards,
        "redemptions": events.filter(event_type=LedgerEvent.REDEEM).count(),
        "repeat_rate": round(returning / active_cards, 4) if active_cards else 0.0,
        **wallet_split(merchant, from_date, to_date),
    }


def wallet_split(
    merchant: Merchant,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict[str, int]:
    """Active wallet registrations by platform, for passes added in the window.

    ``/analytics/summary`` reports the same two counts all-time; this one honours
    the dashboard's date filter, so the Apple-vs-Google chart moves with the rest
    of the page.
    """
    from_date, to_date = _date_range(from_date, to_date)

    counts = {
        row["platform"]: row["value"]
        for row in WalletRegistration.objects.filter(
            customer_card__merchant=merchant,
            is_active=True,
            created_at__date__gte=from_date,
            created_at__date__lte=to_date,
        )
        .values("platform")
        .annotate(value=Count("id"))
    }
    return {
        "apple_count": counts.get(WalletPlatform.APPLE, 0),
        "google_count": counts.get(WalletPlatform.GOOGLE, 0),
    }


def retention(
    merchant: Merchant,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict[str, Any]:
    """Simple day-N retention curve + at-risk count.

    Cohort = customers who had their first event in the requested period.
    ``retained_pct`` on day N = share of the cohort that had any event on the
    day that is exactly N days after their first event. ``at_risk_count`` counts
    active customers whose last event was more than 30 days ago.
    """
    from_date, to_date = _date_range(from_date, to_date)

    # First event date per customer (inside the merchant), computed in Python to
    # avoid the OuterRef scoping pitfalls of reusing the same subquery across
    # CustomerCard and StampLedger querysets.
    first_event_map = {
        row["customer_card_id"]: row["first_event_date"]
        for row in StampLedger.objects.for_merchant(merchant)
        .values("customer_card_id")
        .annotate(first_event_date=Min("created_at__date"))
    }

    cohort_ids = [
        cid
        for cid, first_date in first_event_map.items()
        if first_date is not None and from_date <= first_date <= to_date
    ]
    cohort_size = len(cohort_ids)

    curve: list[dict[str, Any]] = []
    if cohort_size == 0:
        for day in range(8):
            curve.append({"day": day, "retained_pct": 0.0})
    else:
        # For each cohort customer, compute the day-of-cohort for every event.
        retained_by_day: dict[int, set[Any]] = {day: set() for day in range(8)}
        events = (
            StampLedger.objects.for_merchant(merchant)
            .filter(customer_card_id__in=cohort_ids)
            .values("customer_card_id", "created_at__date")
        )
        for event in events:
            cid = event["customer_card_id"]
            first_date = first_event_map[cid]
            event_date = event["created_at__date"]
            if event_date is None or first_date is None:
                continue
            day = (event_date - first_date).days
            if 0 <= day < 8:
                retained_by_day[day].add(cid)

        for day in range(8):
            retained = len(retained_by_day[day])
            curve.append({"day": day, "retained_pct": round(retained / cohort_size, 4)})

    thirty_days_ago = timezone.localdate() - timedelta(days=30)
    at_risk_count = (
        CustomerCard.objects.for_merchant(merchant)
        .filter(
            status=CustomerCardStatus.ACTIVE,
            last_event_at__isnull=False,
            last_event_at__date__lt=thirty_days_ago,
        )
        .count()
    )

    return {"curve": curve, "at_risk_count": at_risk_count}


def by_location(
    merchant: Merchant,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict[str, Any]]:
    """Per-location stamp + redemption counts."""
    from_date, to_date = _date_range(from_date, to_date)

    stamps = (
        _ledger_qs(merchant, from_date, to_date)
        .filter(event_type=LedgerEvent.STAMP)
        .values("location_id")
        .annotate(stamps=Count("id"))
    )
    redemptions = (
        Redemption.objects.for_merchant(merchant)
        .filter(created_at__date__gte=from_date, created_at__date__lte=to_date)
        .values("location_id")
        .annotate(redemptions=Count("id"))
    )

    stamp_map = {row["location_id"]: row["stamps"] for row in stamps}
    redemption_map = {row["location_id"]: row["redemptions"] for row in redemptions}

    results: list[dict[str, Any]] = []
    for loc in Location.objects.for_merchant(merchant).order_by("name"):
        results.append(
            {
                "location_id": str(loc.id),
                "name": loc.name,
                "stamps": stamp_map.get(loc.id, 0),
                "redemptions": redemption_map.get(loc.id, 0),
            }
        )
    return results


def activity_feed(merchant: Merchant, limit: int = 20) -> list[dict[str, Any]]:
    """Recent activity items from the ledger (ENROLL/STAMP/REDEEM)."""
    ledger_rows = list(
        StampLedger.objects.for_merchant(merchant)
        .select_related("customer_card", "staff__user", "location")
        .order_by("-created_at")[:limit]
    )

    def _type_from_ledger(event_type: str) -> str:
        if event_type == LedgerEvent.ENROLL:
            return "join"
        if event_type == LedgerEvent.STAMP:
            return "stamp"
        if event_type == LedgerEvent.REDEEM:
            return "redeem"
        return "stamp"

    merged: list[tuple[datetime, dict[str, Any]]] = []
    for row in ledger_rows:
        item = {
            "type": _type_from_ledger(row.event_type),
            "actor_name": (
                row.staff.user.get_full_name() or row.staff.user.email if row.staff else None
            ),
            "customer_name": row.customer_card.customer_name or None,
            "location": row.location.name if row.location else None,
            "at": row.created_at.isoformat(),
        }
        merged.append((row.created_at, item))

    merged.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in merged[:limit]]
