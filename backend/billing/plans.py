"""Plan catalogue — limits + feature flags per ``PlanTier`` (Phase 1.4).

The frozen contract pins the anti-fraud constants but **not** the per-plan
limits, so this map is billing-owned config (not a contract symbol): tune the
numbers here without a contract PR. ``None`` means *unlimited*.

The entitlements engine (``billing/entitlements.py``) reads this map; the trial
gives full ``TRIAL_PLAN``-level access for ``TRIAL_DAYS`` regardless of the
merchant's stored plan, then locks on expiry without conversion.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

from django.core.cache import cache
from django.db import models

from core.enums import PlanTier


class BillingStatus(models.TextChoices):
    """Lifecycle of a merchant's subscription (billing-owned, not in core)."""

    TRIALING = "TRIALING", "Trialing"
    ACTIVE = "ACTIVE", "Active"
    PAST_DUE = "PAST_DUE", "Past due"
    CANCELED = "CANCELED", "Canceled"
    LOCKED = "LOCKED", "Locked"


# 14-day trial at Growth-level access (brief §1.4).
TRIAL_DAYS = 14
TRIAL_PLAN = PlanTier.GROWTH

# Capability groups. ``max_*`` are counted against live usage; the rest are
# boolean feature flags. Keep in sync with ``entitlements.CAPABILITIES``.
LIMIT_CAPABILITIES = frozenset({"max_cards", "max_locations", "max_staff", "max_customers"})
# ``whatsapp`` is retained but OFF on every plan — wallet push (free) is the
# messaging channel now; the WhatsApp adapter stays dormant (Fawry pattern), so
# the capability and metering keep working should it ever be re-enabled.
# ``specialized_roles`` gates the Marketing/Designer staff roles; ``custom_branding``
# gates custom join-page branding / removing "Powered by Stampn". Both Growth+.
FEATURE_CAPABILITIES = frozenset(
    {"whatsapp", "export", "api", "specialized_roles", "custom_branding"}
)

# plan -> {capability: limit|flag}. ``None`` limit = unlimited.
# ``automations`` (int) and ``analytics`` (basic|full) are display-only features
# surfaced via /me's Entitlements — not gate capabilities, so they are NOT in
# FEATURE_CAPABILITIES and never passed to ``entitlements.check()``.
#
# FREE is not a sellable tier (subscribe offers Starter/Growth/Chain only) — it
# only supplies the display "shape" for a locked/un-converted account, so it
# stays here to avoid a KeyError but grants nothing.
PLAN_LIMITS: dict[str, dict[str, int | bool | str | None]] = {
    PlanTier.FREE: {
        "max_cards": 1,
        "max_locations": 1,
        "max_staff": 2,
        "max_customers": 200,
        "whatsapp": False,
        "export": False,
        "api": False,
        "specialized_roles": False,
        "custom_branding": False,
        "automations": 0,
        "analytics": "basic",
        "whatsapp_quota": 0,
    },
    PlanTier.STARTER: {
        "max_cards": 3,
        "max_locations": 2,
        "max_staff": 5,
        "max_customers": 2_000,
        "whatsapp": False,
        "export": True,
        "api": False,
        "specialized_roles": False,
        "custom_branding": False,
        "automations": 2,
        "analytics": "basic",
        "whatsapp_quota": 0,
    },
    PlanTier.GROWTH: {
        "max_cards": 10,
        "max_locations": 10,
        "max_staff": 25,
        "max_customers": 20_000,
        "whatsapp": False,
        "export": True,
        "api": True,
        "specialized_roles": True,
        "custom_branding": True,
        "automations": 5,
        "analytics": "full",
        "whatsapp_quota": 0,
    },
    PlanTier.CHAIN: {
        "max_cards": None,
        "max_locations": None,
        "max_staff": None,
        "max_customers": None,
        "whatsapp": False,
        "export": True,
        "api": True,
        "specialized_roles": True,
        "custom_branding": True,
        "automations": 99,
        "analytics": "full",
        "whatsapp_quota": None,
    },
}

# Monthly list price per tier, EGP major units (billing-owned config — confirm
# with product before launch, per the brief's notes). ``trial`` shows the plan
# the trial converts to (GROWTH); CHAIN is custom-quoted (0 = "contact us").
PLAN_PRICES_EGP: dict[str, Decimal] = {
    PlanTier.FREE: Decimal("0"),
    PlanTier.STARTER: Decimal("299"),
    PlanTier.GROWTH: Decimal("799"),
    PlanTier.CHAIN: Decimal("0"),
}

# Phase 3 — plan limits AND prices move to the DB (``billing.models.Plan``) so
# admins can edit them without a deploy. ``PLAN_LIMITS`` / ``PLAN_PRICES_EGP``
# above stay as the seed data (a migration loads them) and the fallback below
# when the table is empty/missing a key — e.g. a fresh install before the seed
# migration runs, or isolated unit tests that touch ``billing.plans`` w/o the DB.
_PLAN_CATALOGUE_CACHE_KEY = "billing:plan_catalogue:v2"
_PLAN_CATALOGUE_CACHE_TTL = 60  # seconds; admin edits also invalidate explicitly


class _PlanEntry(TypedDict):
    limits: dict[str, int | bool | str | None]
    price: Decimal


def _catalogue() -> dict[str, _PlanEntry]:
    """DB-backed ``{key: {limits, price}}`` for **all** plans, cached.

    Archived plans are included on purpose: archiving only hides a plan from the
    catalogue *listing* (admin/subscribe UI) — it must not change how an existing
    subscriber's limits or price resolve. Empty (fresh install) -> ``{}`` so the
    accessors below fall back to the hardcoded seed.
    """
    cached = cache.get(_PLAN_CATALOGUE_CACHE_KEY)
    if cached is not None:
        return cached

    from billing.models import Plan  # local import: Plan lives in this app's models

    rows: dict[str, _PlanEntry] = {
        p.key: {"limits": p.as_limits(), "price": p.price_egp} for p in Plan.objects.all()
    }
    cache.set(_PLAN_CATALOGUE_CACHE_KEY, rows, _PLAN_CATALOGUE_CACHE_TTL)
    return rows


def plan_limits_map() -> dict[str, dict[str, int | bool | str | None]]:
    """The live plan -> limits map, DB-backed with the hardcoded seed as fallback."""
    rows = {key: entry["limits"] for key, entry in _catalogue().items()}
    return rows or PLAN_LIMITS


def plan_price(plan: str) -> Decimal:
    """The live monthly price for ``plan`` (what checkout charges), DB-backed."""
    entry = _catalogue().get(plan)
    if entry is not None:
        return entry["price"]
    return PLAN_PRICES_EGP.get(plan, Decimal("0"))


def invalidate_plan_cache() -> None:
    """Call after any ``Plan`` create/update/archive so edits apply immediately."""
    cache.delete(_PLAN_CATALOGUE_CACHE_KEY)
