"""Billing Celery tasks (Phase 1.4)."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from billing.models import Subscription
from billing.plans import BillingStatus

logger = logging.getLogger(__name__)


@shared_task(queue="default")
def expire_trials() -> int:
    """Lock merchants whose trial elapsed without converting. Beat: hourly.

    ``effective_plan`` already treats an expired trial as locked, so this is a
    persistence/bookkeeping pass — it flips the stored status so the lock is
    visible in queries and the dashboard, not just computed on read.

    Under the card-upfront trial this is a *fallback*, not the normal path: a
    trialing merchant with a linked card is auto-charged by Paymob at day 14 and
    converted by the subscription webhook. Reaching here means that charge never
    landed, or the trial never had a card at all.
    """
    locked = Subscription.objects.filter(
        status=BillingStatus.TRIALING, trial_ends_at__lte=timezone.now()
    ).update(status=BillingStatus.LOCKED)
    return locked


@shared_task(queue="default")
def expire_scheduled_cancellations() -> int:
    """Close period-end cancels once the paid period has lapsed. Beat: hourly.

    Flips the stored status to CANCELED — ``effective_plan`` already locks these
    lazily on read — and tells Paymob to close the subscription for good. The
    sub was suspended when the merchant asked to cancel, so this changes nothing
    about what they are charged; it stops a suspended-but-live subscription
    lingering on Paymob's side indefinitely.

    Iterates rather than bulk-updating: each row needs its own gateway call, and
    one merchant's gateway failure must not stop the rest from being closed.
    """
    due = Subscription.objects.filter(
        status=BillingStatus.ACTIVE,
        cancel_at_period_end=True,
        current_period_end__lte=timezone.now(),
    )
    canceled = 0
    for sub in due:
        from billing.services import stop_gateway_billing

        stop_gateway_billing(sub, action="cancel")
        # Local state is authoritative for access and must land regardless of
        # whether Paymob was reachable: the period is over either way. A failed
        # close leaves gateway_billing_stopped False for the retry sweep.
        Subscription.objects.filter(pk=sub.pk).update(
            status=BillingStatus.CANCELED,
            cancel_at_period_end=False,
            updated_at=timezone.now(),
        )
        canceled += 1
    return canceled


@shared_task(queue="default")
def retry_pending_gateway_cancels() -> int:
    """Re-attempt suspends that never reached Paymob. Beat: hourly.

    The failure this exists for: a merchant cancels, we mark it locally, but the
    suspend call fails (Paymob down, timeout, expired token). They believe they
    cancelled while Paymob keeps deducting — the worst outcome in billing, and
    invisible until a chargeback. ``schedule_cancel`` deliberately does not fail
    the merchant's cancellation on a gateway error, so this is what closes the
    loop.

    Suspend is idempotent, so a re-attempt on an already-suspended subscription
    is harmless; ``gateway_billing_stopped`` keeps us from hammering the ones
    that already landed.
    """
    from billing.services import stop_gateway_billing

    pending = Subscription.objects.filter(
        cancel_at_period_end=True,
        gateway_billing_stopped=False,
    ).exclude(paymob_subscription_id="")
    fixed = 0
    for sub in pending:
        if stop_gateway_billing(sub, action="suspend"):
            logger.warning(
                "recovered a failed suspend for subscription %s (merchant %s)",
                sub.paymob_subscription_id,
                sub.merchant_id,
            )
            fixed += 1
    return fixed
