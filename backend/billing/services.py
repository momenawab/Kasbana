"""Billing services (Phase 1.4) — subscription lifecycle helpers.

Pure functions the webhook handlers and the entitlements engine call. The
gateway adapters (Paymob/Fawry) are deferred to the payments slice; these
helpers express the state transitions independent of any provider.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from billing.models import Invoice, InvoiceStatus, Subscription
from billing.plans import BillingStatus
from core.models import Merchant

if TYPE_CHECKING:
    from billing.gateways.base import WebhookEvent


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
def begin_checkout(
    merchant: Merchant, *, plan: str, provider: str, gateway_ref: str
) -> Subscription:
    """Record a pending checkout so the webhook can resolve merchant + plan.

    Does *not* change access — the merchant stays on their current plan/trial
    until the gateway confirms payment via webhook (``activate_plan``).
    """
    sub = subscription_for(merchant)
    sub.provider = provider
    sub.gateway_ref = gateway_ref
    sub.pending_plan = plan
    sub.save(update_fields=["provider", "gateway_ref", "pending_plan", "updated_at"])
    return sub


@transaction.atomic
def lock(merchant: Merchant, *, status: str = BillingStatus.LOCKED) -> Subscription:
    """Lock a merchant (cancel / trial-expiry / past-due). Data is retained."""
    sub = subscription_for(merchant)
    sub.status = status
    sub.save(update_fields=["status", "updated_at"])
    return sub


def subscription_by_gateway_ref(provider: str, gateway_ref: str) -> Subscription | None:
    """Resolve the pending subscription a webhook event belongs to."""
    return Subscription.objects.filter(provider=provider, gateway_ref=gateway_ref).first()


@transaction.atomic
def record_invoice(
    merchant: Merchant,
    *,
    amount_egp: Decimal,
    status: str,
    provider: str = "",
    gateway_ref: str = "",
    pdf_url: str = "",
) -> Invoice:
    """Create (or return existing) an invoice for a gateway transaction.

    Idempotent on ``(provider, gateway_ref)`` so a replayed webhook does not
    duplicate the invoice.
    """
    if gateway_ref:
        existing = Invoice.objects.filter(
            merchant=merchant, provider=provider, gateway_ref=gateway_ref
        ).first()
        if existing is not None:
            return existing
    return Invoice.objects.create(
        merchant=merchant,
        amount_egp=amount_egp,
        status=status,
        provider=provider,
        gateway_ref=gateway_ref,
        pdf_url=pdf_url,
        issued_at=timezone.now(),
    )


@transaction.atomic
def apply_webhook_event(event: WebhookEvent) -> Subscription | None:
    """Drive subscription state from a verified gateway ``WebhookEvent``.

    - ``success``  -> activate the pending plan + record a paid invoice;
    - ``failed``   -> record a failed invoice (access unchanged);
    - ``canceled`` -> lock the merchant (subscription canceled/refunded).

    Returns the affected subscription, or ``None`` when the event cannot be
    matched to a merchant (logged + acknowledged so the gateway stops retrying).
    """
    sub = subscription_by_gateway_ref(event.provider, event.gateway_ref)
    if sub is None and event.merchant_id:
        sub = Subscription.objects.filter(merchant_id=event.merchant_id).first()
    if sub is None:
        return None

    merchant = sub.merchant
    plan = event.plan or sub.pending_plan or sub.plan

    if event.kind == "success":
        amount = event.amount_egp if event.amount_egp is not None else Decimal("0")
        record_invoice(
            merchant,
            amount_egp=amount,
            status=InvoiceStatus.PAID,
            provider=event.provider,
            gateway_ref=event.gateway_ref,
        )
        sub = activate_plan(merchant, plan, provider=event.provider, gateway_ref=event.gateway_ref)
        sub.pending_plan = ""
        sub.save(update_fields=["pending_plan", "updated_at"])
        return sub

    if event.kind == "failed":
        record_invoice(
            merchant,
            amount_egp=event.amount_egp or Decimal("0"),
            status=InvoiceStatus.FAILED,
            provider=event.provider,
            gateway_ref=event.gateway_ref,
        )
        return sub

    if event.kind == "canceled":
        return lock(merchant, status=BillingStatus.CANCELED)

    return sub
