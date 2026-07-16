"""Account services (Phase 1.5) — settings access + contract payload builders."""

from __future__ import annotations

from typing import Any

from django.utils.text import slugify

from accounts.models import MerchantSettings
from billing.plans import BillingStatus
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
    s = settings_for(merchant)
    return {
        "id": str(merchant.id),
        "name": merchant.name,
        "legal_name": merchant.legal_name,
        "slug": merchant.slug,
        "status": status_to_wire(merchant, sub),
        "plan": plan_to_wire(sub),
        # The signup gate (card-upfront trial): they have no card yet, so the
        # trial has not started and nothing is entitled. Distinct from
        # ``status`` — that collapses to "suspended" here, which is true of
        # their *access* but would tell a new merchant an admin banned them.
        "needs_card": sub.status == BillingStatus.PENDING_CARD,
        "trial_ends_at": sub.trial_ends_at,
        "logo_url": merchant.logo_url or None,
        "address": s.address,
        "color_bg": merchant.color_bg,
        "color_fg": merchant.color_fg,
        "enroll_headline": s.enroll_headline,
        "enroll_tagline": s.enroll_tagline,
        "phone": s.contact_phone,
        "facebook_url": s.facebook_url,
        "instagram_url": s.instagram_url,
        "tiktok_url": s.tiktok_url,
        "whatsapp": s.whatsapp,
        "terms_url": s.terms_url,
        "branches": s.branches,
    }
