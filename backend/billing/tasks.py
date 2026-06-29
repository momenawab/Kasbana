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
