"""Computed audience segments (Phase 1.7 + roadmap Phase 2).

Segments are *computed* from the ledger / customer state — not stored. Each has
a stable ``key`` the campaign ``audience`` field references; ``resolve`` returns
the matching ``CustomerCard`` queryset so a campaign can fan out to it.

Built-in keys: ``all``, ``new`` (joined recently), ``active`` (recent activity),
``lapsed`` (no activity in a while), ``reward_ready``, ``birthday_month``. Dynamic
keys: ``card:<id>`` and ``location:<id>``.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import F, QuerySet
from django.utils import timezone

from core.models import Card, CustomerCard, Merchant

LAPSED_DAYS = 30
NEW_DAYS = 7
ACTIVE_DAYS = 30


def _base(merchant: Merchant) -> QuerySet[CustomerCard]:
    return CustomerCard.objects.for_merchant(merchant)


def resolve(merchant: Merchant, key: str) -> QuerySet[CustomerCard]:
    """Return the customers in segment ``key`` (empty queryset if unknown)."""
    qs = _base(merchant)
    now = timezone.now()
    if key == "all":
        return qs
    if key == "new":
        return qs.filter(enrolled_at__gte=now - timedelta(days=NEW_DAYS))
    if key == "active":
        return qs.filter(last_event_at__gte=now - timedelta(days=ACTIVE_DAYS))
    if key == "lapsed":
        cutoff = now - timedelta(days=LAPSED_DAYS)
        return qs.filter(last_event_at__isnull=False, last_event_at__lt=cutoff)
    if key == "reward_ready":
        return qs.filter(stamp_count__gte=F("card__stamps_required"))
    if key == "birthday_month":
        return qs.filter(birthday__month=now.month)
    if key.startswith("card:"):
        return qs.filter(card_id=key.split(":", 1)[1])
    if key.startswith("location:"):
        loc_id = key.split(":", 1)[1]
        return qs.filter(ledger_entries__location_id=loc_id).distinct()
    return qs.none()


def catalogue(merchant: Merchant) -> list[dict[str, object]]:
    """The contract ``Segment`` list: stable audiences with live counts.

    Built-in segments first, then one per card program (``card:<id>``) so a
    merchant can target a single loyalty card's holders.
    """
    builtin = {
        "all": "All customers",
        "new": f"New (joined <{NEW_DAYS}d)",
        "active": f"Active (<{ACTIVE_DAYS}d)",
        "lapsed": f"Lapsed (>{LAPSED_DAYS}d)",
        "reward_ready": "Reward ready",
        "birthday_month": "Birthday this month",
    }
    out: list[dict[str, object]] = [
        {"key": key, "label": label, "count": resolve(merchant, key).count()}
        for key, label in builtin.items()
    ]
    for card in Card.objects.for_merchant(merchant).only("id", "name"):
        out.append(
            {
                "key": f"card:{card.id}",
                "label": f"Card: {card.name}",
                "count": resolve(merchant, f"card:{card.id}").count(),
            }
        )
    return out
