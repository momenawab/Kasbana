"""Billing services (Phase 1.4) — subscription lifecycle helpers.

Pure functions the webhook handlers and the entitlements engine call. The
gateway adapters (Paymob/Fawry) are deferred to the payments slice; these
helpers express the state transitions independent of any provider.
"""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


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
    sub.cancel_at_period_end = False  # a new/renewed subscription clears any pending cancel
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
def schedule_cancel(merchant: Merchant) -> Subscription:
    """Merchant-initiated cancel that keeps access until the period ends.

    The sub stays ACTIVE and fully entitled until ``current_period_end``; after
    that ``Subscription.effective_plan`` locks it (lazy — no cron needed, though
    ``expire_scheduled_cancellations`` tidies the stored status). If there is no
    paid period to run out (no ``current_period_end`` on an active plan), there
    is nothing to wait for, so lock immediately. A trial is left to expire on its
    own ``trial_ends_at`` — we only flag the intent so it won't be reactivated.
    """
    sub = subscription_for(merchant)
    if sub.status == BillingStatus.ACTIVE and sub.current_period_end is None:
        sub.status = BillingStatus.CANCELED
        sub.cancel_at_period_end = False
        sub.save(update_fields=["status", "cancel_at_period_end", "updated_at"])
        return sub
    sub.cancel_at_period_end = True
    sub.save(update_fields=["cancel_at_period_end", "updated_at"])
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


def _add_months(dt: datetime, months: int) -> datetime:
    """Add ``months`` calendar months to ``dt``, clamping the day (stdlib only)."""
    import calendar

    total = dt.month - 1 + months
    year = dt.year + total // 12
    month = total % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


@transaction.atomic
def grant_free_months(merchant: Merchant, months: int) -> Subscription:
    """Grant ``months`` of free paid access by pushing ``current_period_end``
    forward that many calendar months from the later of now / the existing period
    end. A no-op for ``months <= 0``. This is the "free months" primitive the
    referral program (Phase E.1) comps both sides with — distinct from
    ``set_comp`` (unbounded) and ``extend_trial`` (trial, in days)."""
    sub = subscription_for(merchant)
    if months <= 0:
        return sub
    now = timezone.now()
    base = sub.current_period_end
    if base is None or base < now:
        base = now
    sub.current_period_end = _add_months(base, months)
    sub.save(update_fields=["current_period_end", "updated_at"])
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

        # Fire the one-time partner referral reward (Phase E.1). Best-effort and
        # idempotent (guarded by reward_granted) — a reward failure must never
        # fail the payment. Deferred import avoids a billing↔partners cycle.
        try:
            from partners.services import on_merchant_converted

            on_merchant_converted(merchant)
        except Exception:  # pragma: no cover - defensive
            logger.exception("partner reward failed for merchant %s", merchant.id)

        return sub

    if event.kind == "failed":
        record_invoice(
            merchant,
            amount_egp=event.amount_egp or Decimal("0"),
            status=InvoiceStatus.FAILED,
            provider=event.provider,
            gateway_ref=event.gateway_ref,
        )
        # Access is deliberately left unchanged. This system has no recurring
        # auto-renewal (checkouts are one-time), so a failed charge on an ACTIVE
        # merchant is always a *voluntary* upgrade / re-subscribe attempt — it
        # must NOT revoke the plan they already paid for. PAST_DUE (the dunning
        # signal) is reached by an admin, or by a future real renewal system.
        return sub

    if event.kind == "canceled":
        return lock(merchant, status=BillingStatus.CANCELED)

    return sub
