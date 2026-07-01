"""Billing services (Phase 1.4) — subscription lifecycle helpers.

Pure functions the webhook handlers and the entitlements engine call. The
gateway adapters (Paymob/Fawry) are deferred to the payments slice; these
helpers express the state transitions independent of any provider.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import IntegrityError, transaction
from django.utils import timezone

from billing.models import Invoice, InvoiceStatus, Subscription
from billing.plans import BillingStatus
from core.models import Merchant

if TYPE_CHECKING:
    from billing.gateways.base import CheckoutSession, WebhookEvent


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


@transaction.atomic
def unlock(merchant: Merchant) -> Subscription:
    """Resume paid access on the stored plan (admin — opposite of ``lock``)."""
    sub = subscription_for(merchant)
    sub.status = BillingStatus.ACTIVE
    sub.save(update_fields=["status", "updated_at"])
    return sub


@transaction.atomic
def extend_trial(merchant: Merchant, days: int) -> Subscription:
    """Admin trial extension — (re)starts a ``days``-long trial from now."""
    sub = subscription_for(merchant)
    sub.status = BillingStatus.TRIALING
    sub.trial_ends_at = timezone.now() + timedelta(days=days)
    sub.save(update_fields=["status", "trial_ends_at", "updated_at"])
    return sub


@transaction.atomic
def set_comp(merchant: Merchant, on: bool) -> Subscription:
    """Toggle admin-granted free access (bypasses billing ``status``)."""
    sub = subscription_for(merchant)
    sub.comp = on
    sub.save(update_fields=["comp", "updated_at"])
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
    note: str = "",
) -> Invoice:
    """Create (or return existing) an invoice for a gateway transaction.

    Idempotent on ``(provider, gateway_ref)`` so a replayed webhook does not
    duplicate the invoice. A manual/one-off admin entry (Phase 5) passes a blank
    ``gateway_ref`` — exempt from the idempotency lookup and the DB constraint —
    plus a ``note``.
    """
    if gateway_ref:
        existing = Invoice.objects.filter(provider=provider, gateway_ref=gateway_ref).first()
        if existing is not None:
            return existing
    try:
        # Savepoint so a unique-constraint clash (a concurrent duplicate webhook
        # that committed between our check and here) doesn't poison the outer
        # transaction — we recover by returning the row the other request made.
        with transaction.atomic():
            return Invoice.objects.create(
                merchant=merchant,
                amount_egp=amount_egp,
                status=status,
                provider=provider,
                gateway_ref=gateway_ref,
                pdf_url=pdf_url,
                note=note,
                issued_at=timezone.now(),
            )
    except IntegrityError:
        return Invoice.objects.get(provider=provider, gateway_ref=gateway_ref)


@transaction.atomic
def retry_invoice(invoice: Invoice, *, customer_email: str = "") -> CheckoutSession:
    """Admin-triggered retry of a FAILED invoice (Phase 5) — a new checkout at the
    *current* price (not the old invoice's amount, in case an admin edited the
    plan's price since — Phase 3) for the plan the merchant is actually trying
    to be on: ``pending_plan`` if a checkout is still outstanding (e.g. a first-
    subscribe failure while still TRIALING — ``plan`` would default to FREE/0
    there, which is wrong), else the stored ``plan``. ``current_period_end``/
    status only change once the gateway confirms via the normal webhook ->
    ``apply_webhook_event`` path.
    """
    from billing.gateways import get_gateway
    from billing.plans import plan_price

    merchant = invoice.merchant
    sub = subscription_for(merchant)
    plan = sub.pending_plan or sub.plan
    provider = invoice.provider or "paymob"
    gateway = get_gateway(provider)
    session = gateway.create_checkout(
        merchant_id=str(merchant.id),
        plan=plan,
        amount_egp=plan_price(plan),
        customer_email=customer_email,
    )
    begin_checkout(merchant, plan=plan, provider=provider, gateway_ref=session.gateway_ref)
    return session


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
        # Replay guard: if we've already booked a paid invoice for this exact
        # gateway transaction, the plan is already active — acknowledge and stop
        # (no second activation write).
        if (
            event.gateway_ref
            and Invoice.objects.filter(
                provider=event.provider,
                gateway_ref=event.gateway_ref,
                status=InvoiceStatus.PAID,
            ).exists()
        ):
            return sub
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
        # A renewal charge failing on an already-paying merchant is exactly
        # "past due" (Phase 5 dunning signal) — a first-subscribe failure while
        # still TRIALING leaves the trial untouched, they can just retry checkout.
        if sub.status == BillingStatus.ACTIVE:
            sub.status = BillingStatus.PAST_DUE
            sub.save(update_fields=["status", "updated_at"])
        return sub

    if event.kind == "canceled":
        return lock(merchant, status=BillingStatus.CANCELED)

    return sub
