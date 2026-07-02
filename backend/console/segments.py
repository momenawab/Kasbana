"""Audience segment resolution for announcements (Phase 10).

Turns an ``Announcement.Segment`` key (+ optional param) into the set of target
merchants. Cross-tenant by design; reuses the Phase 9 at-risk logic and the
same trial-ending window so targeting matches what the lifecycle screens show.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import QuerySet
from django.utils import timezone

from billing.plans import BillingStatus
from console import lifecycle
from console.models import Announcement
from core.enums import LedgerEvent
from core.models import Merchant, StampLedger

ACTIVE_WINDOW_DAYS = 30


def resolve(audience: str, param: str = "") -> QuerySet[Merchant]:
    """The merchants targeted by ``audience`` (+ ``param``)."""
    now = timezone.now()

    if audience == Announcement.Segment.PLAN and param:
        return Merchant.objects.filter(subscription__plan=param)

    if audience == Announcement.Segment.TRIAL_ENDING:
        return Merchant.objects.filter(
            subscription__status=BillingStatus.TRIALING,
            subscription__trial_ends_at__gt=now,
            subscription__trial_ends_at__lte=now + timedelta(days=lifecycle.TRIAL_ENDING_DAYS),
        )

    if audience == Announcement.Segment.AT_RISK:
        ids = [row["id"] for row in lifecycle.at_risk()]
        return Merchant.objects.filter(id__in=ids)

    if audience == Announcement.Segment.ACTIVE:
        recent = (
            StampLedger.objects.filter(
                event_type=LedgerEvent.STAMP,
                created_at__gte=now - timedelta(days=ACTIVE_WINDOW_DAYS),
            )
            .values_list("merchant_id", flat=True)
            .distinct()
        )
        return Merchant.objects.filter(id__in=list(recent))

    # ALL (and any unknown key) → everyone.
    return Merchant.objects.all()
