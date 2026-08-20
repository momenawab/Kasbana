"""Compliance helpers (Phase 13, PDPL) — data export + delete accounting.

Kept separate from the views so the bundle shape and the delete-snapshot are
testable in isolation. Every merchant-owned row cascades off ``core.Merchant``
(``on_delete=CASCADE`` throughout), so a delete is a single ``merchant.delete()``
— but we snapshot *what* is about to vanish into the audit trail first, because
after the cascade there is nothing left to point an audit row at.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from core.models import (
    Card,
    CustomerCard,
    Location,
    Merchant,
    Redemption,
    Reward,
    StaffUser,
    StampLedger,
    WalletRegistration,
)


def _values(qs: Any) -> list[dict[str, Any]]:
    return list(qs.values())


def export_bundle(merchant: Merchant) -> dict[str, Any]:
    """Every stored record for ``merchant``, as one JSON-serialisable bundle.

    Uses ``.values()`` (raw column dicts) so the bundle is lossless and stays
    decoupled from the wire serializers — this is a data-subject export, not an
    API response, so it should carry everything, not a curated view.
    """
    settings = getattr(merchant, "settings", None)
    subscription = getattr(merchant, "subscription", None)
    return {
        "exported_at": timezone.now().isoformat(),
        "merchant": {
            "id": str(merchant.id),
            "name": merchant.name,
            "slug": merchant.slug,
            "legal_name": merchant.legal_name,
            "status": merchant.status,
            "plan": merchant.plan,
            "created_at": merchant.created_at.isoformat(),
        },
        "settings": (
            {
                "contact_phone": settings.contact_phone,
                "contact_email": settings.contact_email,
                "address": settings.address,
                "language": settings.language,
            }
            if settings
            else None
        ),
        "subscription": (
            {
                "plan": subscription.plan,
                "status": subscription.status,
                "trial_ends_at": subscription.trial_ends_at,
                "current_period_end": subscription.current_period_end,
                "comp": subscription.comp,
            }
            if subscription
            else None
        ),
        "locations": _values(Location.objects.filter(merchant=merchant)),
        "staff": _values(StaffUser.objects.filter(merchant=merchant)),
        "cards": _values(Card.objects.filter(merchant=merchant)),
        "customers": _values(CustomerCard.objects.filter(merchant=merchant)),
        "ledger": _values(StampLedger.objects.filter(merchant=merchant)),
        "rewards": _values(Reward.objects.filter(card__merchant=merchant)),
        "redemptions": _values(Redemption.objects.filter(merchant=merchant)),
        "wallet_registrations": _values(
            WalletRegistration.objects.filter(customer_card__merchant=merchant)
        ),
        "invoices": _values(merchant.invoices.all()),
    }


def delete_snapshot(merchant: Merchant) -> dict[str, Any]:
    """Row counts about to be erased — recorded in the audit trail pre-delete."""
    return {
        "merchant_id": str(merchant.id),
        "merchant_name": merchant.name,
        "merchant_slug": merchant.slug,
        "counts": {
            "locations": Location.objects.filter(merchant=merchant).count(),
            "staff": StaffUser.objects.filter(merchant=merchant).count(),
            "cards": Card.objects.filter(merchant=merchant).count(),
            "customers": CustomerCard.objects.filter(merchant=merchant).count(),
            "ledger": StampLedger.objects.filter(merchant=merchant).count(),
            "redemptions": Redemption.objects.filter(merchant=merchant).count(),
            "invoices": merchant.invoices.count(),
        },
    }
