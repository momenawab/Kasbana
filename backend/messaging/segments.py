"""Computed audience segments (Phase 1.7).

Segments are *computed* from the ledger / customer state — not stored. Each has
a stable ``key`` the campaign ``audience`` field references; ``resolve`` returns
the matching ``CustomerCard`` queryset so a campaign can fan out to it.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import F, QuerySet
from django.utils import timezone

from core.models import CustomerCard, Merchant

LAPSED_DAYS = 30


def _base(merchant: Merchant) -> QuerySet[CustomerCard]:
    return CustomerCard.objects.for_merchant(merchant)


def resolve(merchant: Merchant, key: str) -> QuerySet[CustomerCard]:
    """Return the customers in segment ``key`` (empty queryset if unknown)."""
    qs = _base(merchant)
    if key == "all":
        return qs
    if key == "lapsed":
        cutoff = timezone.now() - timedelta(days=LAPSED_DAYS)
        return qs.filter(last_event_at__isnull=False, last_event_at__lt=cutoff)
    if key == "reward_ready":
        return qs.filter(stamp_count__gte=F("card__stamps_required"))
    if key.startswith("card:"):
        return qs.filter(card_id=key.split(":", 1)[1])
    if key.startswith("location:"):
        loc_id = key.split(":", 1)[1]
        return qs.filter(ledger_entries__location_id=loc_id).distinct()
    return qs.none()


def catalogue(merchant: Merchant) -> list[dict[str, object]]:
    """The contract ``Segment`` list: stable audiences with live counts."""
    base = _base(merchant)
    cutoff = timezone.now() - timedelta(days=LAPSED_DAYS)
    return [
        {"key": "all", "label": "All customers", "count": base.count()},
        {
            "key": "lapsed",
            "label": f"Lapsed (>{LAPSED_DAYS}d)",
            "count": base.filter(last_event_at__isnull=False, last_event_at__lt=cutoff).count(),
        },
        {
            "key": "reward_ready",
            "label": "Reward ready",
            "count": base.filter(stamp_count__gte=F("card__stamps_required")).count(),
        },
    ]
