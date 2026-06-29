"""WhatsApp quota metering (Phase 1.7).

The ``whatsapp`` capability gates *access* (entitlements.check); this module
caps *volume* — a per-merchant per-month counter against the plan's
``whatsapp_quota``. ``ensure_quota`` raises ``PlanLimit`` (402) when exhausted;
``record_send`` increments the counter atomically after a successful enqueue.
"""

from __future__ import annotations

from django.db.models import F

from billing.plans import PLAN_LIMITS
from billing.services import subscription_for
from common.errors import PlanLimit
from core.models import Merchant
from messaging.models import WhatsAppUsage, current_period


def quota_for(merchant: Merchant) -> int | None:
    """The merchant's monthly WhatsApp allowance (``None`` = unlimited)."""
    sub = subscription_for(merchant)
    plan = sub.effective_plan() or sub.plan
    quota = PLAN_LIMITS[plan].get("whatsapp_quota", 0)
    assert quota is None or isinstance(quota, int)
    return quota


def used_this_period(merchant: Merchant) -> int:
    row = WhatsAppUsage.objects.filter(merchant=merchant, period=current_period()).first()
    return row.sent if row else 0


def ensure_quota(merchant: Merchant, *, count: int = 1) -> None:
    """Raise ``PlanLimit`` (402) if sending ``count`` would exceed the quota."""
    quota = quota_for(merchant)
    if quota is None:
        return
    if used_this_period(merchant) + count > quota:
        raise PlanLimit("WhatsApp monthly quota exhausted.")


def record_send(merchant: Merchant, *, count: int = 1) -> None:
    """Increment the month's WhatsApp counter atomically (idempotent get/create)."""
    period = current_period()
    usage, created = WhatsAppUsage.objects.get_or_create(
        merchant=merchant, period=period, defaults={"sent": count}
    )
    if not created:
        WhatsAppUsage.objects.filter(pk=usage.pk).update(sent=F("sent") + count)
