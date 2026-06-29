"""Account services (Phase 1.5) — settings access + contract payload builders."""

from __future__ import annotations

from typing import Any

from django.utils.text import slugify

from accounts.models import MerchantSettings
from billing.services import subscription_for
from billing.wire import plan_to_wire, status_to_wire
from core.models import Merchant


def settings_for(merchant: Merchant) -> MerchantSettings:
    """The merchant's settings row, created lazily. Idempotent."""
    obj, _ = MerchantSettings.objects.get_or_create(merchant=merchant)
    return obj


def unique_slug(name: str) -> str:
    """A unique merchant slug derived from ``name`` (``-2``, ``-3`` on collision)."""
    base = slugify(name) or "merchant"
    slug, n = base, 1
    while Merchant.objects.filter(slug=slug).exists():
        n += 1
        slug = f"{base}-{n}"
    return slug


def merchant_payload(merchant: Merchant) -> dict[str, Any]:
    """Contract ``Merchant`` object with wire-mapped ``plan`` / ``status``."""
    sub = subscription_for(merchant)
    return {
        "id": str(merchant.id),
        "name": merchant.name,
        "slug": merchant.slug,
        "status": status_to_wire(merchant, sub),
        "plan": plan_to_wire(sub),
        "trial_ends_at": sub.trial_ends_at,
        "logo_url": merchant.logo_url or None,
        "color_bg": merchant.color_bg,
        "color_fg": merchant.color_fg,
    }
