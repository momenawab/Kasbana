"""Revenue & financial analytics tests (Phase 7).

Covers the Finance/Super-admin gate (Support + Read-only 403'd, unlike the rest
of the console), MRR/ARR/ARPU accuracy vs the raw subscription + catalogue data,
revenue-by-plan, trial→paid conversion, cumulative logo/revenue churn, the
monthly collected-revenue series + new-payers, cohort retention, NRR across two
adjacent periods, the date-range filter, and the CSV export.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from billing.models import Invoice, InvoiceStatus, Subscription
from billing.plans import BillingStatus, plan_price
from billing.services import subscription_for
from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminUser
from core.enums import PlanTier
from tests import factories

pytestmark = pytest.mark.django_db

URL = "/api/admin/v1/analytics/revenue"
EXPORT_URL = "/api/admin/v1/analytics/revenue/export"


@pytest.fixture
def super_admin():
    a = AdminUser(email="super@stampn.net", role=AdminRole.SUPER_ADMIN)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def finance_admin():
    a = AdminUser(email="finance@stampn.net", role=AdminRole.FINANCE)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def support_admin():
    a = AdminUser(email="support@stampn.net", role=AdminRole.SUPPORT)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def readonly_admin():
    a = AdminUser(email="ro@stampn.net", role=AdminRole.READ_ONLY)
    a.set_password("supersecret1")
    a.save()
    return a


def _bearer(client, admin):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return client


def _paying_merchant(plan=PlanTier.GROWTH):
    """A merchant with an ACTIVE, non-comp subscription on ``plan`` + a PAID invoice."""
    m = factories.MerchantFactory()
    sub = subscription_for(m)
    sub.plan = plan
    sub.status = BillingStatus.ACTIVE
    sub.comp = False
    sub.save()
    Invoice.objects.create(
        merchant=m, amount_egp=plan_price(plan), status=InvoiceStatus.PAID, provider="paymob"
    )
    return m


def _trialing_merchant():
    """A merchant with the default fresh (active) trial subscription."""
    m = factories.MerchantFactory()
    subscription_for(m)  # default status TRIALING, trial_ends_at = now + 14d
    return m


# ── role gate ───────────────────────────────────────────────────────────────
def test_unauthenticated_rejected(api_client):
    assert api_client.get(URL).status_code == 401


def test_finance_admin_allowed(api_client, finance_admin):
    assert _bearer(api_client, finance_admin).get(URL).status_code == 200


def test_super_admin_allowed(api_client, super_admin):
    assert _bearer(api_client, super_admin).get(URL).status_code == 200


def test_support_admin_forbidden(api_client, support_admin):
    assert _bearer(api_client, support_admin).get(URL).status_code == 403


def test_readonly_admin_forbidden(api_client, readonly_admin):
    assert _bearer(api_client, readonly_admin).get(URL).status_code == 403


def test_export_gated_to_finance(api_client, support_admin, finance_admin):
    assert _bearer(api_client, support_admin).get(EXPORT_URL).status_code == 403
    assert _bearer(api_client, finance_admin).get(EXPORT_URL).status_code == 200


# ── MRR / ARR / ARPU accuracy ─────────────────────────────────────────────────
def test_mrr_arr_arpu_match_raw_data(api_client, finance_admin):
    _paying_merchant(PlanTier.GROWTH)
    _paying_merchant(PlanTier.STARTER)
    expected_mrr = plan_price(PlanTier.GROWTH) + plan_price(PlanTier.STARTER)

    kpis = _bearer(api_client, finance_admin).get(URL).json()["kpis"]
    assert Decimal(kpis["mrr"]) == expected_mrr
    assert Decimal(kpis["arr"]) == expected_mrr * 12
    assert Decimal(kpis["arpu"]) == (expected_mrr / 2).quantize(Decimal("0.01"))
    assert kpis["paying_merchants"] == 2


def test_comp_and_trial_excluded_from_mrr(api_client, finance_admin):
    _paying_merchant(PlanTier.GROWTH)
    # A comp'd merchant on GROWTH — free access, must not add to MRR.
    comp = factories.MerchantFactory()
    comp_sub = subscription_for(comp)
    comp_sub.plan = PlanTier.GROWTH
    comp_sub.status = BillingStatus.ACTIVE
    comp_sub.comp = True
    comp_sub.save()
    # A trialing merchant — no MRR.
    _trialing_merchant()

    kpis = _bearer(api_client, finance_admin).get(URL).json()["kpis"]
    assert Decimal(kpis["mrr"]) == plan_price(PlanTier.GROWTH)
    assert kpis["paying_merchants"] == 1
    assert kpis["comped_merchants"] == 1
    assert kpis["active_trials"] >= 1


def test_revenue_by_plan(api_client, finance_admin):
    _paying_merchant(PlanTier.GROWTH)
    _paying_merchant(PlanTier.GROWTH)
    _paying_merchant(PlanTier.STARTER)

    resp = _bearer(api_client, finance_admin).get(URL).json()
    rows = {r["plan"]: r for r in resp["revenue_by_plan"]}
    assert rows[PlanTier.GROWTH]["paying_merchants"] == 2
    assert Decimal(rows[PlanTier.GROWTH]["mrr"]) == plan_price(PlanTier.GROWTH) * 2
    assert rows[PlanTier.STARTER]["paying_merchants"] == 1


# ── conversion + churn ─────────────────────────────────────────────────────────
def test_trial_to_paid_conversion(api_client, finance_admin):
    # 2 merchants ever paid; 1 still in a fresh trial (not eligible yet).
    _paying_merchant(PlanTier.GROWTH)
    _paying_merchant(PlanTier.STARTER)
    _trialing_merchant()

    kpis = _bearer(api_client, finance_admin).get(URL).json()["kpis"]
    # eligible = total(3) - active_trials(1) = 2; converted = 2 → 1.0
    assert kpis["trial_to_paid_conversion"] == pytest.approx(1.0)


def test_logo_and_revenue_churn(api_client, finance_admin):
    _paying_merchant(PlanTier.GROWTH)  # still paying
    # A merchant who paid once then got locked → churned.
    churned = _paying_merchant(PlanTier.STARTER)
    Subscription.objects.filter(merchant=churned).update(status=BillingStatus.LOCKED)

    kpis = _bearer(api_client, finance_admin).get(URL).json()["kpis"]
    # ever_paid = 2, currently paying = 1 → logo churn 0.5
    assert kpis["logo_churn_rate"] == pytest.approx(0.5)
    assert 0 < kpis["revenue_churn_rate"] < 1


# ── monthly series + new payers ────────────────────────────────────────────────
def test_monthly_series_and_new_payers(api_client, finance_admin):
    m = _paying_merchant(PlanTier.GROWTH)
    # Backdate the single paid invoice into last month.
    last_month = timezone.now() - timedelta(days=32)
    Invoice.objects.filter(merchant=m).update(issued_at=last_month)

    data = _bearer(api_client, finance_admin).get(URL).json()
    series = data["monthly_series"]
    assert len(series) >= 1
    total_new = sum(row["new_payers"] for row in series)
    assert total_new == 1
    total_invoices = sum(row["paid_invoices"] for row in series)
    assert total_invoices == 1


# ── cohort retention ───────────────────────────────────────────────────────────
def test_cohort_retention(api_client, finance_admin):
    _paying_merchant(PlanTier.GROWTH)
    factories.MerchantFactory()  # signed up, not paying

    cohorts = _bearer(api_client, finance_admin).get(URL).json()["cohort_retention"]
    total_size = sum(c["size"] for c in cohorts)
    total_paying = sum(c["still_paying"] for c in cohorts)
    assert total_size == 2
    assert total_paying == 1


# ── date range + export ────────────────────────────────────────────────────────
def test_date_range_filter_scopes_series(api_client, finance_admin):
    m = _paying_merchant(PlanTier.GROWTH)
    old = timezone.now() - timedelta(days=400)
    Invoice.objects.filter(merchant=m).update(issued_at=old)

    # Default window is 12 months → the 400-day-old invoice is out of range.
    data = _bearer(api_client, finance_admin).get(URL).json()
    assert sum(row["paid_invoices"] for row in data["monthly_series"]) == 0

    # Widen the range to include it.
    frm = (date.today() - timedelta(days=500)).isoformat()
    data2 = _bearer(api_client, finance_admin).get(URL, {"from": frm}).json()
    assert sum(row["paid_invoices"] for row in data2["monthly_series"]) == 1


def test_csv_export_content(api_client, finance_admin):
    m = _paying_merchant(PlanTier.GROWTH)
    Invoice.objects.filter(merchant=m).update(issued_at=timezone.now())

    resp = _bearer(api_client, finance_admin).get(EXPORT_URL)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert "attachment; filename=" in resp["Content-Disposition"]
    body = resp.content.decode()
    assert body.splitlines()[0] == "month,collected_egp,paid_invoices,new_payers"


def test_empty_platform_is_zeroed(api_client, finance_admin):
    kpis = _bearer(api_client, finance_admin).get(URL).json()["kpis"]
    assert Decimal(kpis["mrr"]) == 0
    assert kpis["paying_merchants"] == 0
    assert kpis["ltv"] is None
    assert kpis["net_revenue_retention"] is None


# ── MRR normalises what a subscription is actually worth per month ────────────
def test_an_annual_subscriber_counts_as_a_twelfth_of_the_annual_price(api_client, finance_admin):
    """Annual is ten months' money for twelve months' service, so counting an
    annual subscriber at the monthly list price overstates them by ~20%."""
    from billing.plans import BillingInterval

    m = _paying_merchant(PlanTier.GROWTH)
    sub = subscription_for(m)
    sub.billing_interval = BillingInterval.ANNUAL
    sub.save()

    kpis = _bearer(api_client, finance_admin).get(URL).json()["kpis"]

    # 9,990/yr → 832.50/mo, not Growth's 999 monthly list price.
    assert Decimal(kpis["mrr"]) == Decimal("832.50")


def test_monthly_and_annual_subscribers_sum_correctly(api_client, finance_admin):
    from billing.plans import BillingInterval

    _paying_merchant(PlanTier.GROWTH)  # 999/mo
    annual = _paying_merchant(PlanTier.STARTER)
    sub = subscription_for(annual)
    sub.billing_interval = BillingInterval.ANNUAL
    sub.save()

    body = _bearer(api_client, finance_admin).get(URL).json()

    # 999 + (5,990 ÷ 12 = 499.17)
    assert Decimal(body["kpis"]["mrr"]) == Decimal("1498.17")
    rows = {r["plan"]: r for r in body["revenue_by_plan"]}
    assert Decimal(rows["STARTER"]["mrr"]) == Decimal("499.17")
    assert Decimal(rows["GROWTH"]["mrr"]) == Decimal("999.00")
