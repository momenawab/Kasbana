"""Contract wire-format mapping for plan / status (Phase 1.5).

The frozen ``core`` enums are uppercase (``PlanTier{FREE,STARTER,GROWTH,CHAIN}``,
``MerchantStatus{ACTIVE,SUSPENDED}``); the contract emits lowercase values and a
``trial`` value that is a ``billing.Subscription`` state, not a ``PlanTier``.
This module is the single place that translates — used by every serializer that
emits ``Merchant`` / ``BillingState`` / ``Entitlements``. No ``core`` change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from billing.plans import BillingStatus
from core.enums import MerchantStatus, PlanTier

if TYPE_CHECKING:
    from billing.models import Subscription
    from core.models import Merchant

# Paid tiers map straight to their lowercase name; FREE has no contract value
# (the pre-paid state is expressed as "trial").
_PAID_WIRE: dict[str, str] = {
    PlanTier.STARTER: "starter",
    PlanTier.GROWTH: "growth",
    PlanTier.CHAIN: "chain",
}


def plan_to_wire(subscription: Subscription) -> str:
    """Contract plan value: ``trial|starter|growth|chain`` (no ``free``)."""
    return _PAID_WIRE.get(subscription.plan, "trial")


def status_to_wire(merchant: Merchant, subscription: Subscription) -> str:
    """Contract status value: ``trial|active|suspended``."""
    if merchant.status == MerchantStatus.SUSPENDED:
        return "suspended"
    if subscription.status == BillingStatus.TRIALING and subscription.trial_active():
        return "trial"
    if subscription.status in (
        BillingStatus.LOCKED,
        BillingStatus.CANCELED,
        BillingStatus.PAST_DUE,
        # No card yet — locked out at the onboarding gate. The contract has no
        # value for the pre-trial state, and "suspended" is what it means for
        # access, so it maps here rather than falling through to "active".
        BillingStatus.PENDING_CARD,
    ):
        return "suspended"
    return "active"
