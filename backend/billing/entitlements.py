"""billing/entitlements.py — plan gating seam (Momen brief §"You implement").

Joe's dashboard (Phase 1.3) calls ``check()`` / ``enforce()`` to gate card,
location, staff and customer creation, plus feature flags. Phase 1.0 ships a
permissive stub so Joe can code against the interface; Phase 1.4 fills in the
``plan -> {limits + features}`` map and real metering.

Capabilities: ``max_cards``, ``max_locations``, ``max_staff``, ``max_customers``,
``whatsapp``, ``export``, ``api``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from common.errors import PlanLimit

if TYPE_CHECKING:
    from core.models import Merchant

CAPABILITIES = frozenset(
    {
        "max_cards",
        "max_locations",
        "max_staff",
        "max_customers",
        "whatsapp",
        "export",
        "api",
    }
)


def check(merchant: Merchant, capability: str) -> bool:
    """Return whether ``merchant`` may use ``capability``.

    STUB (Phase 1.0): always True. Phase 1.4 evaluates the plan map + usage.
    """
    return True


def enforce(merchant: Merchant, capability: str) -> None:
    """Raise ``PlanLimit`` (-> PLAN_LIMIT) if the capability is not allowed.

    STUB (Phase 1.0): never raises. Phase 1.4 enforces real limits.
    """
    if not check(merchant, capability):
        raise PlanLimit()
