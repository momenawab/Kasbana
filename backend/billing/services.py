"""Billing services (Phase 1.4) — subscription lifecycle helpers.

Pure functions the webhook handlers and the entitlements engine call. The
gateway adapters (Paymob/Fawry) are deferred to the payments slice; these
helpers express the state transitions independent of any provider.
"""

from __future__ import annotations

from datetime import datetime

from django.db import transaction

from billing.models import Subscription
from billing.plans import BillingStatus
from core.models import Merchant


def subscription_for(merchant: Merchant) -> Subscription:
    """The merchant's subscription, starting a 14-day trial on first access.

    Merchants created before billing existed have no row yet; the trial clock
    starts now for them (``default_trial_end``). Idempotent.
    """
    sub, _ = Subscription.objects.get_or_create(merchant=merchant, defaults={"plan": merchant.plan})
    return sub


@transaction.atomic
def activate_plan(
    merchant: Merchant,
    plan: str,
    *,
    provider: str = "",
    gateway_ref: str = "",
    period_end: datetime | None = None,
) -> Subscription:
    """Convert a merchant to a paid ``plan`` (subscribe / upgrade / downgrade).

    Mirrors the plan onto ``Merchant.plan`` so the rest of the app can read it
    cheaply; ``Subscription`` remains the source of truth for access.
    """
    sub = subscription_for(merchant)
    sub.plan = plan
    sub.status = BillingStatus.ACTIVE
    if provider:
        sub.provider = provider
    if gateway_ref:
        sub.gateway_ref = gateway_ref
    sub.current_period_end = period_end
    sub.save()

    if merchant.plan != plan:
        merchant.plan = plan
        merchant.save(update_fields=["plan"])
    return sub


@transaction.atomic
def lock(merchant: Merchant, *, status: str = BillingStatus.LOCKED) -> Subscription:
    """Lock a merchant (cancel / trial-expiry / past-due). Data is retained."""
    sub = subscription_for(merchant)
    sub.status = status
    sub.save(update_fields=["status", "updated_at"])
    return sub
