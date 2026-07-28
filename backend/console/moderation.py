"""Content moderation — heuristic flagging + queue helpers (Phase 9).

The heuristic scan is deliberately simple and transparent: it flags a card or
merchant whose public-facing text contains a banned keyword. It's idempotent —
a pending flag for the same (target, reason) is only raised once (DB constraint)
— so re-running the scan never piles up duplicates. Reports (``source=report``)
can also create flags; both land in the same review queue.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction

from console.models import ContentFlag
from console.merchants import real_merchants
from core.models import Card, Merchant

# Lowercased substrings that warrant a human look. Intentionally small + obvious;
# the real value is the review workflow, not an exhaustive filter.
BANNED_KEYWORDS = ["casino", "porn", "xxx", "scam", "counterfeit", "replica"]


def _match(text: str) -> str | None:
    low = (text or "").lower()
    for kw in BANNED_KEYWORDS:
        if kw in low:
            return kw
    return None


def _raise_flag(
    *, merchant: Merchant, target_type: str, target_id: str | UUID, label: str, reason: str
) -> bool:
    """Create a pending flag; a no-op if an identical pending one already exists."""
    try:
        with transaction.atomic():
            ContentFlag.objects.create(
                merchant=merchant,
                target_type=target_type,
                target_id=str(target_id),
                label=label[:200],
                reason=reason,
                source=ContentFlag.Source.HEURISTIC,
            )
        return True
    except IntegrityError:
        return False  # already flagged + pending


def run_scan() -> dict[str, int]:
    """Scan cards + merchant names for banned keywords; returns counts."""
    created = 0
    scanned_cards = 0
    for card in Card.objects.select_related("merchant"):
        scanned_cards += 1
        text = f"{card.name} {card.reward_title} {card.reward_description}"
        kw = _match(text)
        if kw and _raise_flag(
            merchant=card.merchant,
            target_type=ContentFlag.TargetType.CARD,
            target_id=card.id,
            label=card.name,
            reason=f"banned keyword: {kw}",
        ):
            created += 1

    scanned_merchants = 0
    for merchant in real_merchants():
        scanned_merchants += 1
        kw = _match(f"{merchant.name} {merchant.legal_name}")
        if kw and _raise_flag(
            merchant=merchant,
            target_type=ContentFlag.TargetType.MERCHANT,
            target_id=merchant.id,
            label=merchant.name,
            reason=f"banned keyword: {kw}",
        ):
            created += 1

    return {
        "created": created,
        "scanned_cards": scanned_cards,
        "scanned_merchants": scanned_merchants,
    }


def flag_row(flag: ContentFlag) -> dict[str, Any]:
    return {
        "id": flag.id,
        "merchant": {
            "id": flag.merchant_id,
            "name": flag.merchant.name,
            "slug": flag.merchant.slug,
        },
        "target_type": flag.target_type,
        "target_id": flag.target_id,
        "label": flag.label,
        "reason": flag.reason,
        "source": flag.source,
        "status": flag.status,
        "resolution_notes": flag.resolution_notes,
        "created_at": flag.created_at,
        "resolved_at": flag.resolved_at,
    }
