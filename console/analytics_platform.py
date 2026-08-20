"""Platform analytics & usage for the admin console (Phase 8).

Non-financial operational insight: merchant lifecycle counts, platform-wide
loyalty totals, wallet split, feature adoption, growth over time, an
acquisition funnel, and an activity leaderboard. All **aggregates only** (no
PII), so any admin may read (unlike the Finance-gated revenue analytics).

Every number is a live cross-tenant aggregate over the raw tables — the console
models use ``TenantManager``, whose default ``objects`` manager is *unscoped*
(scoping is opt-in via ``for_merchant``), so these queries deliberately see all
merchants.

**Not included:** geographic/city distribution — there is no structured city
field today (``Location`` has only a freeform ``address`` + optional lat/lng),
so a trustworthy breakdown isn't derivable. It lands when a city field does.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.core.cache import cache
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accounts.models import MerchantSettings
from billing.models import Invoice, InvoiceStatus, Subscription
from billing.plans import BillingStatus
from console.merchants import real_merchants
from core.enums import CardType, LedgerEvent, MerchantStatus, WalletPlatform
from core.models import Card, CustomerCard, Redemption, StampLedger, WalletRegistration
from messaging.models import Automation, Campaign

_CACHE_TTL = 300  # seconds
_CACHE_KEY = "console:analytics:platform"


def _distinct_merchants(qs) -> int:
    return qs.values("merchant").distinct().count()


def platform_analytics() -> dict[str, Any]:
    """The full platform-usage payload (cached; point-in-time)."""
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached

    now = timezone.now()
    total_merchants = real_merchants().count()

    # ── merchant lifecycle (subscription state + suspension) ────────────────────
    merchants = {
        "total": total_merchants,
        "active": Subscription.objects.filter(status=BillingStatus.ACTIVE).count(),
        "trialing": Subscription.objects.filter(
            status=BillingStatus.TRIALING, trial_ends_at__gt=now
        ).count(),
        "past_due": Subscription.objects.filter(status=BillingStatus.PAST_DUE).count(),
        "churned": Subscription.objects.filter(
            status__in=[BillingStatus.LOCKED, BillingStatus.CANCELED]
        ).count(),
        "suspended": real_merchants().filter(status=MerchantStatus.SUSPENDED).count(),
    }

    # ── platform-wide loyalty totals ────────────────────────────────────────────
    totals = {
        "customers": CustomerCard.objects.count(),
        "cards": Card.objects.count(),
        "stamps": StampLedger.objects.filter(event_type=LedgerEvent.STAMP).count(),
        "redemptions": Redemption.objects.count(),
    }

    # ── wallet split (active passes) ────────────────────────────────────────────
    wallet_rows = (
        WalletRegistration.objects.filter(is_active=True).values("platform").annotate(n=Count("id"))
    )
    wallet_counts = {row["platform"]: row["n"] for row in wallet_rows}
    wallet = {
        "apple": wallet_counts.get(WalletPlatform.APPLE, 0),
        "google": wallet_counts.get(WalletPlatform.GOOGLE, 0),
    }

    # ── feature adoption (# and % of merchants using each) ──────────────────────
    def pct(n: int) -> float:
        return (n / total_merchants) if total_merchants else 0.0

    adoption_counts = {
        "referrals": _distinct_merchants(Card.objects.filter(referral_enabled=True)),
        "points": _distinct_merchants(Card.objects.filter(type=CardType.POINTS)),
        "automations": _distinct_merchants(Automation.objects.filter(enabled=True)),
        "branded_enroll": MerchantSettings.objects.filter(
            Q(enroll_headline__gt="") | Q(enroll_tagline__gt="")
        ).count(),
        "campaigns": _distinct_merchants(Campaign.objects.all()),
    }
    feature_adoption = [
        {"key": key, "merchants": count, "pct": pct(count)}
        for key, count in adoption_counts.items()
    ]

    # ── growth over time (merchant signups by month, cumulative) ────────────────
    signup_rows = (
        real_merchants()
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(n=Count("id"))
        .order_by("month")
    )
    growth = []
    running = 0
    for row in signup_rows:
        running += row["n"]
        month: datetime = row["month"]
        growth.append(
            {"month": month.strftime("%Y-%m"), "new_merchants": row["n"], "cumulative": running}
        )

    # ── acquisition funnel ──────────────────────────────────────────────────────
    activated = _distinct_merchants(Card.objects.all())  # built ≥1 loyalty program
    paying = _distinct_merchants(Invoice.objects.filter(status=InvoiceStatus.PAID))
    funnel = [
        {"stage": "signed_up", "count": total_merchants},
        {"stage": "activated", "count": activated},
        {"stage": "active_access", "count": merchants["active"] + merchants["trialing"]},
        {"stage": "paying", "count": paying},
    ]

    # ── activity leaderboard (top merchants by loyalty events) ──────────────────
    top_rows = (
        StampLedger.objects.values("merchant").annotate(events=Count("id")).order_by("-events")[:10]
    )
    top_ids = [r["merchant"] for r in top_rows]
    names = {m.id: m for m in real_merchants().filter(id__in=top_ids)}
    customers_by_merchant = {
        r["merchant"]: r["n"]
        for r in CustomerCard.objects.filter(merchant_id__in=top_ids)
        .values("merchant")
        .annotate(n=Count("id"))
    }
    top_merchants = []
    for r in top_rows:
        m = names.get(r["merchant"])
        if m is None:
            continue
        top_merchants.append(
            {
                "id": m.id,
                "name": m.name,
                "slug": m.slug,
                "activity": r["events"],
                "customers": customers_by_merchant.get(m.id, 0),
            }
        )

    payload = {
        "merchants": merchants,
        "totals": totals,
        "wallet": wallet,
        "feature_adoption": feature_adoption,
        "growth": growth,
        "funnel": funnel,
        "top_merchants": top_merchants,
    }
    cache.set(_CACHE_KEY, payload, _CACHE_TTL)
    return payload
