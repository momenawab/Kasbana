"""billing/entitlements.py — the plan-gating engine (Phase 1.4).

The seam Joe's dashboard (Phase 1.3) and the rest of the app call to gate
actions. ``check()`` answers "may this merchant do X right now?"; ``enforce()``
turns a *no* into ``PlanLimit`` (-> ``PLAN_LIMIT`` / HTTP 402).

Resolution (see ``Subscription.effective_plan``):
- locked (trial expired / canceled / past-due) -> every capability denied;
- ``max_*`` limit -> allowed while *current usage < limit* (``None`` = unlimited);
- feature flag (``whatsapp``/``export``/``api``) -> the plan's boolean.

Replaces the Phase 1.0 permissive stub. The signature is unchanged, so Joe's
call sites (`enforce(merchant, "max_cards")`, `check(merchant, "export")`) light
up without any edit to ``dashboard/``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from billing.plans import (
    FEATURE_CAPABILITIES,
    LIMIT_CAPABILITIES,
    PLAN_LIMITS,
)
from billing.services import subscription_for
from common.errors import PlanLimit
from core.models import Card, CustomerCard, Location, StaffUser

if TYPE_CHECKING:
    from core.models import Merchant

CAPABILITIES = LIMIT_CAPABILITIES | FEATURE_CAPABILITIES

# How to count live usage for each ``max_*`` capability (tenant-scoped).
_USAGE_COUNTERS: dict[str, Callable[[Merchant], int]] = {
    "max_cards": lambda m: Card.objects.for_merchant(m).count(),
    "max_locations": lambda m: Location.objects.for_merchant(m).count(),
    "max_staff": lambda m: StaffUser.objects.for_merchant(m).count(),
    "max_customers": lambda m: CustomerCard.objects.for_merchant(m).count(),
}


def check(merchant: Merchant, capability: str) -> bool:
    """Return whether ``merchant`` may use ``capability`` right now."""
    if capability not in CAPABILITIES:
        raise ValueError(f"Unknown capability: {capability!r}")

    plan = subscription_for(merchant).effective_plan()
    if plan is None:  # locked — trial expired or subscription inactive
        return False

    limits = PLAN_LIMITS[plan]
    if capability in FEATURE_CAPABILITIES:
        return bool(limits[capability])

    cap = limits[capability]
    if cap is None:  # unlimited
        return True
    assert isinstance(cap, int)  # LIMIT_CAPABILITIES values are int|None
    return _USAGE_COUNTERS[capability](merchant) < cap


def enforce(merchant: Merchant, capability: str) -> None:
    """Raise ``PlanLimit`` (-> ``PLAN_LIMIT``, HTTP 402) if not allowed."""
    if not check(merchant, capability):
        raise PlanLimit()


def usage(merchant: Merchant) -> dict[str, int | None]:
    """Live tenant-scoped usage counts (drives /me and /billing)."""
    # Imported lazily: ``messaging`` depends on ``billing`` (metering reads the
    # plan quota), so a module-level import would be circular.
    from messaging import metering

    return {
        "cards": _USAGE_COUNTERS["max_cards"](merchant),
        "locations": _USAGE_COUNTERS["max_locations"](merchant),
        "staff": _USAGE_COUNTERS["max_staff"](merchant),
        "customers": _USAGE_COUNTERS["max_customers"](merchant),
        "whatsapp_used": metering.used_this_period(merchant),
        "whatsapp_quota": metering.quota_for(merchant),
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
    limits = PLAN_LIMITS[plan]
    return {
        "plan": plan_to_wire(sub),
        "limits": {k: limits[k] for k in LIMIT_CAPABILITIES},
        "features": {
            "whatsapp": bool(limits["whatsapp"]),
            "export": bool(limits["export"]),
            "api": bool(limits["api"]),
            "automations": limits["automations"],
            "analytics": limits["analytics"],
        },
        "usage": usage(merchant),
    }
