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
FEATURE_CAPABILITIES = frozenset({"whatsapp", "export", "api"})

# plan -> {capability: limit|flag}. ``None`` limit = unlimited.
# ``automations`` (int) and ``analytics`` (basic|full) are display-only features
# surfaced via /me's Entitlements — not gate capabilities, so they are NOT in
# FEATURE_CAPABILITIES and never passed to ``entitlements.check()``.
# ``whatsapp_quota`` is the monthly WhatsApp send allowance (``None`` = unlimited);
# the ``whatsapp`` flag gates access, the quota caps volume (Phase 1.7 metering).
PLAN_LIMITS: dict[str, dict[str, int | bool | str | None]] = {
    PlanTier.FREE: {
        "max_cards": 1,
        "max_locations": 1,
        "max_staff": 2,
        "max_customers": 200,
        "whatsapp": False,
        "export": False,
        "api": False,
        "automations": 0,
        "analytics": "basic",
        "whatsapp_quota": 0,
    },
    PlanTier.STARTER: {
        "max_cards": 3,
        "max_locations": 2,
        "max_staff": 5,
        "max_customers": 2_000,
        "whatsapp": True,
        "export": True,
        "api": False,
        "automations": 2,
        "analytics": "basic",
        "whatsapp_quota": 500,
    },
    PlanTier.GROWTH: {
        "max_cards": 10,
        "max_locations": 10,
        "max_staff": 25,
        "max_customers": 20_000,
        "whatsapp": True,
        "export": True,
        "api": True,
        "automations": 5,
        "analytics": "full",
        "whatsapp_quota": 2_000,
    },
    PlanTier.CHAIN: {
        "max_cards": None,
        "max_locations": None,
        "max_staff": None,
        "max_customers": None,
        "whatsapp": True,
        "export": True,
        "api": True,
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
