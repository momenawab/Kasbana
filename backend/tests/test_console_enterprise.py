"""Admin-side Enterprise assignment (§12, step 4).

An admin agreeing a deal is the only way onto Enterprise — it is not on the
self-serve catalogue. What matters here is that assigning records the agreement
without charging or entitling anyone, and that it cannot leave a merchant on
the tier without a plan (which grants nothing).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from billing import entitlements, services
from billing.models import Plan, Subscription
from billing.plans import BillingStatus, invalidate_plan_cache
from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser
from core.enums import PlanTier

pytestmark = pytest.mark.django_db


def _url(merchant):
    return f"/api/admin/v1/merchants/{merchant.id}/subscription/enterprise"


def _bearer(client, admin):
    tokens = issue_admin_tokens(admin)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.fixture
def finance_admin():
    admin = AdminUser(email="finance@stampn.net", name="Finance", role=AdminRole.FINANCE)
    admin.set_password("supersecret1")
    admin.save()
    return admin


@pytest.fixture
def support_admin():
    admin = AdminUser(email="support@stampn.net", name="Support", role=AdminRole.SUPPORT)
    admin.set_password("supersecret1")
    admin.save()
    return admin


@pytest.fixture
def gold():
    plan = Plan.objects.create(
        key="ENT_GOLD",
        name="Enterprise Gold",
        price_egp=Decimal("7500"),
        price_egp_annual=Decimal("75000"),
        is_public=False,
        api=True,
        priority_support=True,
        analytics="full",
    )
    invalidate_plan_cache()
    return plan


# ── Assigning ───────────────────────────────────────────────────────────────
def test_finance_admin_can_assign_an_enterprise_plan(api_client, finance_admin, merchant, gold):
    resp = _bearer(api_client, finance_admin).post(
        _url(merchant),
        {"plan_key": "ENT_GOLD", "reason": "signed 12mo deal"},
        format="json",
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["plan_name"] == "Enterprise Gold"
    assert Decimal(body["price_egp"]) == Decimal("7500")
    sub = Subscription.objects.get(merchant=merchant)
    assert sub.plan == PlanTier.ENTERPRISE
    assert sub.enterprise_plan == gold


def test_assigning_annual_prices_the_year(api_client, finance_admin, merchant, gold):
    resp = _bearer(api_client, finance_admin).post(
        _url(merchant),
        {"plan_key": "ENT_GOLD", "interval": "annual", "reason": "annual deal"},
        format="json",
    )

    assert Decimal(resp.json()["price_egp"]) == Decimal("75000")
    assert Subscription.objects.get(merchant=merchant).pending_interval == "annual"


def test_assigning_does_not_charge_or_entitle(api_client, finance_admin, merchant, gold):
    """Sales agreeing terms is not payment. They pay through the ordinary
    checkout and activate on the webhook, like everyone else."""
    _bearer(api_client, finance_admin).post(
        _url(merchant), {"plan_key": "ENT_GOLD", "reason": "deal"}, format="json"
    )

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.status == BillingStatus.TRIALING  # untouched
    assert sub.current_period_end is None  # nothing paid for yet


def test_the_merchant_gets_the_negotiated_entitlements_once_active(
    api_client, finance_admin, merchant, gold
):
    _bearer(api_client, finance_admin).post(
        _url(merchant), {"plan_key": "ENT_GOLD", "reason": "deal"}, format="json"
    )
    services.activate_plan(merchant, PlanTier.ENTERPRISE)  # what the webhook does

    # API is off on every public tier — it is what Enterprise re-enables.
    assert entitlements.check(merchant, "api") is True


def test_reassigning_moves_them_to_the_new_deal(api_client, finance_admin, merchant, gold):
    Plan.objects.create(
        key="ENT_PLATINUM", name="Enterprise Platinum", price_egp=Decimal("15000"), is_public=False
    )
    invalidate_plan_cache()
    client = _bearer(api_client, finance_admin)
    client.post(_url(merchant), {"plan_key": "ENT_GOLD", "reason": "first"}, format="json")

    resp = client.post(
        _url(merchant), {"plan_key": "ENT_PLATINUM", "reason": "upsold"}, format="json"
    )

    assert resp.json()["plan_name"] == "Enterprise Platinum"
    assert Subscription.objects.get(merchant=merchant).enterprise_plan.key == "ENT_PLATINUM"


# ── Guardrails ──────────────────────────────────────────────────────────────
def test_a_public_plan_is_rejected(api_client, finance_admin, merchant):
    """Assigning Growth here would leave them on tier ENTERPRISE resolving to
    Growth's limits — a state with no legitimate meaning."""
    resp = _bearer(api_client, finance_admin).post(
        _url(merchant), {"plan_key": "GROWTH", "reason": "oops"}, format="json"
    )

    assert resp.status_code == 400
    assert Subscription.objects.get(merchant=merchant).plan != PlanTier.ENTERPRISE


def test_an_archived_plan_is_rejected(api_client, finance_admin, merchant, gold):
    gold.archived = True
    gold.save()
    invalidate_plan_cache()

    resp = _bearer(api_client, finance_admin).post(
        _url(merchant), {"plan_key": "ENT_GOLD", "reason": "stale"}, format="json"
    )

    assert resp.status_code == 400


def test_an_unknown_plan_404s(api_client, finance_admin, merchant):
    resp = _bearer(api_client, finance_admin).post(
        _url(merchant), {"plan_key": "NOPE", "reason": "typo"}, format="json"
    )

    assert resp.status_code == 404


def test_a_reason_is_required(api_client, finance_admin, merchant, gold):
    """Every subscription mutation is auditable; a money decision especially."""
    resp = _bearer(api_client, finance_admin).post(
        _url(merchant), {"plan_key": "ENT_GOLD"}, format="json"
    )

    assert resp.status_code == 400


def test_support_admin_cannot_assign(api_client, support_admin, merchant, gold):
    """Pricing is Finance/Super-admin only, like every other plan mutation."""
    resp = _bearer(api_client, support_admin).post(
        _url(merchant), {"plan_key": "ENT_GOLD", "reason": "nope"}, format="json"
    )

    assert resp.status_code == 403


def test_the_assignment_is_audited(api_client, finance_admin, merchant, gold):
    _bearer(api_client, finance_admin).post(
        _url(merchant), {"plan_key": "ENT_GOLD", "reason": "signed 12mo deal"}, format="json"
    )

    row = AdminAuditLog.objects.get(action="subscription.assign_enterprise")
    assert row.actor_email == "finance@stampn.net"
    assert row.metadata["reason"] == "signed 12mo deal"
    assert row.metadata["after"]["enterprise_plan_key"] == "ENT_GOLD"


# ── The admin can see which deal a merchant is on ───────────────────────────
def test_the_subscription_view_names_the_deal(api_client, finance_admin, merchant, gold):
    """``plan`` reads ENTERPRISE for everyone negotiated — useless on its own."""
    _bearer(api_client, finance_admin).post(
        _url(merchant), {"plan_key": "ENT_GOLD", "reason": "deal"}, format="json"
    )

    body = (
        _bearer(api_client, finance_admin)
        .get(f"/api/admin/v1/merchants/{merchant.id}/subscription")
        .json()
    )

    assert body["plan"] == PlanTier.ENTERPRISE
    assert body["enterprise_plan_key"] == "ENT_GOLD"
    assert body["enterprise_plan_name"] == "Enterprise Gold"


def test_a_public_tier_names_no_deal(api_client, finance_admin, merchant):
    services.activate_plan(merchant, PlanTier.GROWTH)

    body = (
        _bearer(api_client, finance_admin)
        .get(f"/api/admin/v1/merchants/{merchant.id}/subscription")
        .json()
    )

    assert body["enterprise_plan_key"] == ""
    assert body["enterprise_plan_name"] == ""


def test_patching_to_enterprise_does_not_500(api_client, finance_admin, merchant):
    """The tier has no catalogue row of its own, so the downgrade guardrail
    used to KeyError on it rather than reading as deny-all."""
    resp = _bearer(api_client, finance_admin).patch(
        f"/api/admin/v1/merchants/{merchant.id}/subscription",
        {"plan": PlanTier.ENTERPRISE, "reason": "manual"},
        format="json",
    )

    assert resp.status_code in (200, 409)  # not a 500
