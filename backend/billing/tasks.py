"""Billing Celery tasks (Phase 1.4)."""

from __future__ import annotations

from celery import shared_task
from django.utils import timezone

from billing.models import Subscription
from billing.plans import BillingStatus


@shared_task(queue="default")
def expire_trials() -> int:
    """Lock merchants whose trial elapsed without converting. Beat: hourly.

    ``effective_plan`` already treats an expired trial as locked, so this is a
    persistence/bookkeeping pass — it flips the stored status so the lock is
    visible in queries and the dashboard, not just computed on read.
    """
    locked = Subscription.objects.filter(
        status=BillingStatus.TRIALING, trial_ends_at__lte=timezone.now()
    ).update(status=BillingStatus.LOCKED)
    return locked


@shared_task(queue="default")
def expire_scheduled_cancellations() -> int:
    """Flip period-end cancels to CANCELED once the paid period has lapsed.

    ``Subscription.effective_plan`` already locks these lazily on read, so this
    is a persistence/bookkeeping pass — it makes the cancellation visible in
    queries and the dashboard instead of only computed at access-check time.
    """
    canceled = Subscription.objects.filter(
        status=BillingStatus.ACTIVE,
        cancel_at_period_end=True,
        current_period_end__lte=timezone.now(),
    ).update(status=BillingStatus.CANCELED, cancel_at_period_end=False)
    return canceled
