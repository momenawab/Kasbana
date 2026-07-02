"""Merchant lifecycle pipeline + at-risk / health scoring (Phase 9).

Both are computed live from the raw subscription + activity + invoice data — no
stored ``health_score`` column (which would need a snapshot job to stay fresh);
this is always current and cross-tenant. Read-only, any admin.

- **Pipeline stage** (mutually exclusive): ``churned`` → ``active`` → ``trial``
  → ``lead``, evaluated in that order.
- **Health score** (0–100): starts at 100, each risk signal subtracts; a
  merchant is *at risk* below ``AT_RISK_THRESHOLD``. Churned merchants are past
  risk (already lost) and are excluded from the at-risk list.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Max
from django.utils import timezone

from billing.models import Invoice, InvoiceStatus, Subscription
from billing.plans import BillingStatus
from core.models import Merchant, StampLedger

AT_RISK_THRESHOLD = 70
LOW_ACTIVITY_DAYS = 14
TRIAL_ENDING_DAYS = 3


def _stage(sub: Subscription | None, now) -> str:
    if sub is None:
        return "lead"  # signed up, never even materialised a subscription
    if sub.status in (BillingStatus.LOCKED, BillingStatus.CANCELED):
        return "churned"
    if sub.status == BillingStatus.TRIALING and not sub.trial_active(now):
        return "churned"  # trial expired without converting
    if sub.comp or sub.status == BillingStatus.ACTIVE:
        return "active"
    if sub.status == BillingStatus.TRIALING:
        return "trial"
    return "lead"


def pipeline() -> dict[str, Any]:
    """Merchants bucketed by lifecycle stage (counts + a sample per stage)."""
    now = timezone.now()
    subs = {s.merchant_id: s for s in Subscription.objects.select_related("merchant")}
    stages: dict[str, list[dict[str, Any]]] = {
        "lead": [],
        "trial": [],
        "active": [],
        "churned": [],
    }
    for m in Merchant.objects.all().order_by("-created_at"):
        stage = _stage(subs.get(m.id), now)
        stages[stage].append({"id": m.id, "name": m.name, "slug": m.slug})

    return {
        "stages": [
            {"stage": stage, "count": len(rows), "merchants": rows[:25]}
            for stage, rows in stages.items()
        ]
    }


def _health(merchant: Merchant, sub: Subscription | None, now, last_activity) -> dict[str, Any]:
    score = 100
    reasons: list[str] = []

    # Each signal is a genuine churn risk that on its own drops the score below
    # AT_RISK_THRESHOLD (70) so it surfaces; combined signals compound.
    if sub is not None and sub.status == BillingStatus.PAST_DUE:
        score -= 40
        reasons.append("past due")
    if (
        sub is not None
        and sub.status == BillingStatus.TRIALING
        and sub.trial_active(now)
        and sub.trial_ends_at is not None
        and sub.trial_ends_at <= now + timedelta(days=TRIAL_ENDING_DAYS)
    ):
        score -= 35
        reasons.append("trial ending")
    if last_activity is None or last_activity < now - timedelta(days=LOW_ACTIVITY_DAYS):
        score -= 35
        reasons.append("low activity")

    # A failed charge more recent than any successful one = a payment problem.
    last_paid = (
        Invoice.objects.filter(merchant=merchant, status=InvoiceStatus.PAID)
        .order_by("-issued_at")
        .values_list("issued_at", flat=True)
        .first()
    )
    last_failed = (
        Invoice.objects.filter(merchant=merchant, status=InvoiceStatus.FAILED)
        .order_by("-issued_at")
        .values_list("issued_at", flat=True)
        .first()
    )
    if last_failed is not None and (last_paid is None or last_failed > last_paid):
        score -= 35
        reasons.append("failed payment")

    return {"score": max(0, score), "reasons": reasons}


def at_risk() -> list[dict[str, Any]]:
    """Non-churned merchants with a health score below the threshold, worst first."""
    now = timezone.now()
    subs = {s.merchant_id: s for s in Subscription.objects.select_related("merchant")}

    # Last loyalty activity per merchant (single grouped query).
    last_activity: dict[Any, Any] = {}
    for row in StampLedger.objects.values("merchant").annotate(last=Max("created_at")):
        last_activity[row["merchant"]] = row["last"]

    rows: list[dict[str, Any]] = []
    for m in Merchant.objects.all():
        sub = subs.get(m.id)
        if _stage(sub, now) == "churned":
            continue
        health = _health(m, sub, now, last_activity.get(m.id))
        if health["score"] < AT_RISK_THRESHOLD:
            rows.append(
                {
                    "id": m.id,
                    "name": m.name,
                    "slug": m.slug,
                    "health_score": health["score"],
                    "reasons": health["reasons"],
                }
            )
    rows.sort(key=lambda r: r["health_score"])
    return rows
