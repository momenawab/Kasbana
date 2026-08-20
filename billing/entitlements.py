"""billing/entitlements.py — the plan-gating engine (Phase 1.4).

The seam Joe's dashboard (Phase 1.3) and the rest of the app call to gate
actions. ``check()`` answers "may this merchant do X right now?"; ``enforce()``
turns a *no* into ``PlanLimit`` (-> ``PLAN_LIMIT`` / HTTP 402).

Resolution (see ``Subscription.effective_plan``):
- locked (trial expired / canceled / past-due) -> every capability denied;
- ``max_*`` limit -> allowed while *current usage < limit* (``None`` = unlimited);
- feature flag (``export``/``api``) -> the plan's boolean.

Replaces the Phase 1.0 permissive stub. The signature is unchanged, so Joe's
call sites (`enforce(merchant, "max_cards")`, `check(merchant, "export")`) light
up without any edit to ``dashboard/``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from billing.plans import (
    DERIVED_CAPABILITIES,
    FEATURE_CAPABILITIES,
    LIMIT_CAPABILITIES,
    PLAN_LIMITS,
    PlanLimits,
    plan_limits_map,
)
from billing.services import subscription_for
from common.errors import PlanLimit
from core.models import Card, CustomerCard, Location, StaffUser

if TYPE_CHECKING:
    from core.models import Merchant

CAPABILITIES = LIMIT_CAPABILITIES | FEATURE_CAPABILITIES | DERIVED_CAPABILITIES


def _campaigns_this_month(merchant: Merchant) -> int:
    """Campaigns created since the 1st of the current month, merchant's clock.

    Deliberately a rolling *calendar* month rather than a lifetime total: the
    cap paces sending, so it has to reset. Uses local time — a merchant reads
    "10 campaigns this month" against their own calendar, not UTC's.
    """
    from django.utils import timezone

    from messaging.models import Campaign

    start = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return Campaign.objects.for_merchant(merchant).filter(created_at__gte=start).count()


# How to count live usage for each ``max_*`` capability (tenant-scoped).
_USAGE_COUNTERS: dict[str, Callable[[Merchant], int]] = {
    "max_cards": lambda m: Card.objects.for_merchant(m).count(),
    "max_locations": lambda m: Location.objects.for_merchant(m).count(),
    "max_staff": lambda m: StaffUser.objects.for_merchant(m).count(),
    "max_customers": lambda m: CustomerCard.objects.for_merchant(m).count(),
    "max_campaigns_per_month": _campaigns_this_month,
}


def _limits_for(plan: str) -> PlanLimits:
    """The capability map for a catalogue ``plan`` key.

    DB first, then the hardcoded seed — an active subscription whose plan was
    archived out of the catalogue must keep working, not 500.

    An unrecognised key grants **nothing** rather than raising. That is not
    theoretical: ``PlanTier.ENTERPRISE`` is a tier with no catalogue row of its
    own (the negotiated plan is the row), so a subscription mid-assignment
    resolves here. Failing closed leaves a merchant briefly un-entitled;
    KeyError would 500 every gated request they make.
    """
    from_db = plan_limits_map().get(plan)
    if from_db:
        return from_db
    seeded = PLAN_LIMITS.get(plan)
    if seeded is not None:
        return seeded
    # Nothing known about this key. NB a ``None`` limit means *unlimited*, so
    # zeroing them is what denies; ``None`` here would grant everything.
    denied: PlanLimits = dict.fromkeys(LIMIT_CAPABILITIES, 0)
    denied.update(dict.fromkeys(FEATURE_CAPABILITIES, False))
    denied["analytics"] = "basic"
    denied["automations"] = 0
    denied["custom_features"] = {}
    return denied


def check(merchant: Merchant, capability: str) -> bool:
    """Return whether ``merchant`` may use ``capability`` right now."""
    if capability not in CAPABILITIES:
        raise ValueError(f"Unknown capability: {capability!r}")

    plan = subscription_for(merchant).effective_plan()
    if plan is None:  # locked — trial expired or subscription inactive
        return False

    limits = _limits_for(plan)
    if capability in FEATURE_CAPABILITIES:
        return bool(limits[capability])
    if capability in DERIVED_CAPABILITIES:  # analytics_full: the plan's tier == "full"
        return limits.get("analytics") == "full"

    cap = limits[capability]
    if cap is None:  # unlimited
        return True
    assert isinstance(cap, int)  # LIMIT_CAPABILITIES values are int|None
    return _USAGE_COUNTERS[capability](merchant) < cap


def enforce(merchant: Merchant, capability: str) -> None:
    """Raise ``PlanLimit`` (-> ``PLAN_LIMIT``, HTTP 402) if not allowed."""
    if not check(merchant, capability):
        raise PlanLimit()


def custom_feature(merchant: Merchant, name: str, default: object = None) -> object:
    """A negotiated Enterprise capability from the plan's ``custom_features``.

    Separate from ``check()`` on purpose: that raises on an unknown capability,
    which is what you want for a fixed vocabulary — a typo must not silently
    deny (or grant) access. ``custom_features`` is free-form by design, so an
    absent key is a legitimate "not negotiated" and returns ``default``.
    """
    sub = subscription_for(merchant)
    plan = sub.effective_plan()
    if plan is None:  # locked — a negotiated extra is still an entitlement
        return default
    limits = _limits_for(plan)
    features: object = limits.get("custom_features") or {}
    if not isinstance(features, dict):  # a hand-edited plan row; don't explode
        return default
    return features.get(name, default)


def usage(merchant: Merchant) -> dict[str, int | None]:
    """Live tenant-scoped usage counts (drives /me and /billing)."""
    return {
        "cards": _USAGE_COUNTERS["max_cards"](merchant),
        "locations": _USAGE_COUNTERS["max_locations"](merchant),
        "staff": _USAGE_COUNTERS["max_staff"](merchant),
        "customers": _USAGE_COUNTERS["max_customers"](merchant),
        # Resets on the 1st — the limit it pairs with is per-month.
        "campaigns_this_month": _USAGE_COUNTERS["max_campaigns_per_month"](merchant),
    }


def describe(merchant: Merchant) -> dict[str, object]:
    """Full Entitlements snapshot for ``GET /me`` (contract ``Entitlements``).

    Display-only: shows the limits/features of the plan currently in force
    (Growth-level during the trial; the locked merchant still sees their stored
    plan's shape). Gating decisions go through ``check()`` / ``enforce()``.
    """
    from billing.wire import plan_to_wire

    sub = subscription_for(merchant)
    plan = sub.effective_plan() or sub.plan  # locked -> show stored plan's shape
    limits = _limits_for(plan)
    return {
        "plan": plan_to_wire(sub),
        "limits": {k: limits[k] for k in LIMIT_CAPABILITIES},
        "features": {
            "export": bool(limits["export"]),
            "api": bool(limits["api"]),
            "specialized_roles": bool(limits["specialized_roles"]),
            "custom_branding": bool(limits["custom_branding"]),
            "referral": bool(limits["referral"]),
            "priority_support": bool(limits.get("priority_support")),
            # Negotiated extras, free-form by design. Always an object so the
            # dashboard can iterate it without a null check.
            "custom_features": limits.get("custom_features") or {},
            "automations": limits["automations"],
            "analytics": limits["analytics"],
        },
        "usage": usage(merchant),
    }
