"""Revenue & financial analytics for the admin console (Phase 7).

Every number here is a **pure, reproducible function of the raw
subscription + invoice data** — no separate metrics store. Two honesty notes:

- **MRR is modelled**, not billed monthly: it's the committed monthly value of
  every *currently paying* subscription (``status=ACTIVE``, not ``comp``, not a
  free plan) priced at the live catalogue price (Phase 3). An annual subscriber
  counts as a twelfth of the annual price, and an Enterprise merchant at their
  negotiated plan's price — see ``_monthly_value``. Trials and comps contribute
  0. ARR = MRR × 12; ARPU = MRR ÷ paying merchants.
- **Churn is cumulative (lifetime), not a period rate**: a merchant is churned
  if they *ever* paid (≥1 PAID invoice) but hold no paying subscription now.
  A true period churn rate needs periodic MRR snapshots, which don't exist yet
  (a future snapshot job would make it exact) — so we report what the ledger
  can prove today. **NRR** is the one range-scoped retention figure: collected
  invoices this period from merchants who also paid the *prior* equal period,
  over that prior period's collections.

The whole payload is cached for a short TTL (analytics tolerate mild staleness).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from django.core.cache import cache
from django.db.models.functions import TruncMonth
from django.utils import timezone

from billing.models import Invoice, InvoiceStatus, Subscription
from billing.plans import BillingInterval, BillingStatus, plan_price
from core.enums import PlanTier
from console.merchants import real_merchants
from core.models import Merchant

_CACHE_TTL = 300  # seconds


def _is_paying(sub: Subscription) -> bool:
    """A subscription that contributes to MRR: actively paying a non-free plan."""
    return sub.status == BillingStatus.ACTIVE and not sub.comp and sub.plan != PlanTier.FREE


def _monthly_value(sub: Subscription) -> Decimal:
    """What ``sub`` contributes to MRR — *per month*, whatever it bills on.

    An annual subscriber pays once for twelve months of service, so a twelfth
    of the annual price is their monthly recurring value. Using the monthly list
    price instead would overstate them by ~20%, since annual is deliberately ten
    months' money for twelve months' service.

    Keyed on ``plan_key``: the ENTERPRISE tier has no catalogue row, so pricing
    off ``plan`` would value every negotiated merchant at 0.
    """
    price = plan_price(sub.plan_key, sub.billing_interval)
    if sub.billing_interval == BillingInterval.ANNUAL:
        price = price / 12
    return price.quantize(Decimal("0.01"))


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def revenue_analytics(date_from: date, date_to: date) -> dict[str, Any]:
    """Compute the full revenue payload for the ``[date_from, date_to]`` window.

    Point-in-time metrics (MRR/paying/churn) reflect *now*; the monthly series,
    NRR and collected totals are scoped to the range.
    """
    cache_key = f"console:analytics:revenue:{date_from.isoformat()}:{date_to.isoformat()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # select_related: plan_key follows the enterprise_plan FK, which would
    # otherwise be a query per Enterprise subscriber.
    subs = list(Subscription.objects.select_related("enterprise_plan").all())
    paying = [s for s in subs if _is_paying(s)]
    paying_ids = {s.merchant_id for s in paying}

    # ── MRR / ARR / ARPU + revenue by plan ─────────────────────────────────────
    # Summed per subscription rather than price × headcount: two merchants on
    # the same plan can be worth different monthly amounts, because an annual
    # one is counted at a twelfth of the annual price. Grouping is by plan_key,
    # so the table splits per Enterprise deal (Gold vs Platinum) rather than
    # collapsing them into one meaningless bucket.
    by_plan = Counter(s.plan_key for s in paying)
    mrr_by_plan: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for sub in paying:
        mrr_by_plan[sub.plan_key] += _monthly_value(sub)

    mrr: Decimal = sum(mrr_by_plan.values(), Decimal("0"))
    revenue_by_plan = [
        {"plan": plan, "paying_merchants": count, "mrr": mrr_by_plan[plan]}
        for plan, count in sorted(by_plan.items())
    ]
    arr = mrr * 12
    arpu = (mrr / len(paying)) if paying else Decimal("0")

    active_trials = sum(1 for s in subs if s.status == BillingStatus.TRIALING and s.trial_active())
    comped = sum(1 for s in subs if s.comp)

    # ── conversion + churn (from the invoice ledger) ───────────────────────────
    ever_paid_ids = set(
        Invoice.objects.filter(status=InvoiceStatus.PAID).values_list("merchant_id", flat=True)
    )
    total_merchants = real_merchants().count()
    # Eligible to have converted = everyone who isn't still inside a live trial.
    eligible = total_merchants - active_trials
    trial_to_paid_conversion = (len(ever_paid_ids) / eligible) if eligible > 0 else 0.0

    churned_ids = ever_paid_ids - paying_ids
    logo_churn_rate = (len(churned_ids) / len(ever_paid_ids)) if ever_paid_ids else 0.0

    # Revenue churn: the modelled MRR of churned merchants (their last plan)
    # over total ever-paid MRR.
    churned_mrr: Decimal = sum(
        (
            _monthly_value(s)
            for s in subs
            if s.merchant_id in churned_ids and s.plan != PlanTier.FREE
        ),
        Decimal("0"),
    )
    revenue_churn_rate = (
        float(churned_mrr / (churned_mrr + mrr)) if (churned_mrr + mrr) > 0 else 0.0
    )

    # ── LTV (rough): ARPU ÷ cumulative logo churn ──────────────────────────────
    ltv = (arpu / Decimal(str(logo_churn_rate))) if logo_churn_rate > 0 else None

    # ── monthly series over the range (collected invoices) ─────────────────────
    start_dt = timezone.make_aware(datetime.combine(date_from, time.min))
    end_dt = timezone.make_aware(datetime.combine(date_to, time.max))
    paid_in_range = (
        Invoice.objects.filter(status=InvoiceStatus.PAID, issued_at__range=(start_dt, end_dt))
        .annotate(month=TruncMonth("issued_at"))
        .values_list("month", "amount_egp")
    )
    collected_by_month: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    count_by_month: dict[str, int] = defaultdict(int)
    for month, amount in paid_in_range:
        key = _month_key(month)
        collected_by_month[key] += amount
        count_by_month[key] += 1

    # New payers per month = merchants whose FIRST-ever paid invoice lands there.
    first_paid: dict[Any, datetime] = {}
    for merchant_id, issued_at in Invoice.objects.filter(status=InvoiceStatus.PAID).values_list(
        "merchant_id", "issued_at"
    ):
        if merchant_id not in first_paid or issued_at < first_paid[merchant_id]:
            first_paid[merchant_id] = issued_at
    new_payers_by_month: dict[str, int] = defaultdict(int)
    for issued_at in first_paid.values():
        if start_dt <= issued_at <= end_dt:
            new_payers_by_month[_month_key(issued_at)] += 1

    months = sorted(set(collected_by_month) | set(new_payers_by_month))
    monthly_series = [
        {
            "month": m,
            "collected_egp": collected_by_month.get(m, Decimal("0")),
            "paid_invoices": count_by_month.get(m, 0),
            "new_payers": new_payers_by_month.get(m, 0),
        }
        for m in months
    ]

    # ── NRR: this period's collections from merchants who paid the prior equal
    #    period, over that prior period's total collections ──────────────────────
    period_days = (date_to - date_from).days or 1
    prior_start = start_dt - timedelta(days=period_days)
    prior_payers_rows = Invoice.objects.filter(
        status=InvoiceStatus.PAID, issued_at__range=(prior_start, start_dt)
    ).values_list("merchant_id", "amount_egp")
    prior_payers: set[Any] = set()
    prior_collected = Decimal("0")
    for merchant_id, amount in prior_payers_rows:
        prior_payers.add(merchant_id)
        prior_collected += amount
    current_from_returning = sum(
        (
            amount
            for merchant_id, amount in Invoice.objects.filter(
                status=InvoiceStatus.PAID, issued_at__range=(start_dt, end_dt)
            ).values_list("merchant_id", "amount_egp")
            if merchant_id in prior_payers
        ),
        Decimal("0"),
    )
    net_revenue_retention = (
        float(current_from_returning / prior_collected) if prior_collected > 0 else None
    )

    # ── cohort retention by signup month ───────────────────────────────────────
    cohorts: dict[str, dict[str, int]] = defaultdict(lambda: {"size": 0, "still_paying": 0})
    for m in real_merchants().values_list("id", "created_at"):
        merchant_id, created_at = m
        key = _month_key(created_at)
        cohorts[key]["size"] += 1
        if merchant_id in paying_ids:
            cohorts[key]["still_paying"] += 1
    cohort_retention = [
        {
            "cohort_month": key,
            "size": data["size"],
            "still_paying": data["still_paying"],
            "retention_pct": (data["still_paying"] / data["size"]) if data["size"] else 0.0,
        }
        for key, data in sorted(cohorts.items())
    ]

    payload = {
        "range": {"from": date_from, "to": date_to},
        "kpis": {
            "mrr": mrr,
            "arr": arr,
            "arpu": arpu,
            "ltv": ltv,
            "paying_merchants": len(paying),
            "active_trials": active_trials,
            "comped_merchants": comped,
            "trial_to_paid_conversion": trial_to_paid_conversion,
            "logo_churn_rate": logo_churn_rate,
            "revenue_churn_rate": revenue_churn_rate,
            "net_revenue_retention": net_revenue_retention,
        },
        "revenue_by_plan": revenue_by_plan,
        "monthly_series": monthly_series,
        "cohort_retention": cohort_retention,
    }
    cache.set(cache_key, payload, _CACHE_TTL)
    return payload
