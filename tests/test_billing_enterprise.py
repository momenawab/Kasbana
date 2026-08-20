"""Enterprise: the negotiated tier (§12).

The tier says *that* a merchant is Enterprise; the enterprise_plan FK says
*which* deal. What matters here is that the two stay consistent — the merchant
must be billed and entitled by the plan an admin actually agreed with them, not
by whatever the client asks for.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from billing import entitlements, services
from billing.gateways.base import CheckoutSession
from billing.models import Plan, Subscription
from billing.plans import BillingInterval, BillingStatus, invalidate_plan_cache
from billing.wire import plan_to_wire
from core.enums import PlanTier, Role
from tests import factories

pytestmark = pytest.mark.django_db


class FakeGateway:
    provider = "paymob"
    calls: list[dict] = []

    def create_checkout(self, **kwargs):
        FakeGateway.calls.append(kwargs)
        return CheckoutSession(checkout_url="https://pay.example/x", gateway_ref="order-ent")


@pytest.fixture(autouse=True)
def gateway(monkeypatch):
    FakeGateway.calls = []
    monkeypatch.setattr("billing.views.get_gateway", lambda provider="paymob": FakeGateway())


@pytest.fixture
def gold():
    plan = Plan.objects.create(
        key="ENT_GOLD",
        name="Enterprise Gold",
        price_egp=Decimal("7500"),
        price_egp_annual=Decimal("75000"),
        is_public=False,
        max_cards=None,
        max_locations=None,
        max_staff=None,
        max_customers=None,
        export=True,
        api=True,
        specialized_roles=True,
        custom_branding=True,
        referral=True,
        priority_support=True,
        analytics="full",
        automations=99,
        paymob_plan_id_monthly="pm-ent-30",
        paymob_plan_id_annual="pm-ent-360",
    )
    invalidate_plan_cache()
    return plan


def _client(merchant):
    from rest_framework_simplejwt.tokens import RefreshToken

    staff = factories.StaffUserFactory(merchant=merchant, role=Role.OWNER)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(staff.user).access_token}"
    )
    return client


# ── Assignment ──────────────────────────────────────────────────────────────
def test_assigning_records_the_tier_and_the_plan(merchant, gold):
    sub = services.assign_enterprise_plan(merchant, gold)

    assert sub.plan == PlanTier.ENTERPRISE  # the tier
    assert sub.enterprise_plan == gold  # which deal
    merchant.refresh_from_db()
    assert merchant.plan == PlanTier.ENTERPRISE  # mirrored for cheap reads


def test_assigning_does_not_grant_access_or_take_money(merchant, gold):
    """Sales agreeing a deal is not payment. They are billed by the ordinary
    flow — an admin sends the checkout link and the webhook activates them."""
    sub = services.assign_enterprise_plan(merchant, gold)

    assert sub.status == BillingStatus.TRIALING  # untouched
    assert FakeGateway.calls == []


def test_assigning_mid_trial_does_not_cut_the_trial_short(merchant, gold):
    services.assign_enterprise_plan(merchant, gold)

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.trial_active() is True
    # ...and the trial now runs at the negotiated plan's limits.
    assert sub.effective_plan() == "ENT_GOLD"


def test_a_public_plan_cannot_be_assigned_as_enterprise(merchant):
    """It would leave them on tier ENTERPRISE resolving to Growth's limits —
    a state with no legitimate meaning."""
    growth = Plan.objects.get(key=PlanTier.GROWTH)

    with pytest.raises(ValueError, match="is a public plan"):
        services.assign_enterprise_plan(merchant, growth)


def test_an_archived_plan_cannot_be_assigned(merchant, gold):
    gold.archived = True
    gold.save()

    with pytest.raises(ValueError, match="archived"):
        services.assign_enterprise_plan(merchant, gold)


def test_reassigning_moves_them_to_the_new_deal(merchant, gold):
    services.assign_enterprise_plan(merchant, gold)
    platinum = Plan.objects.create(
        key="ENT_PLATINUM", name="Enterprise Platinum", price_egp=Decimal("15000"), is_public=False
    )
    invalidate_plan_cache()

    sub = services.assign_enterprise_plan(merchant, platinum)

    assert sub.enterprise_plan == platinum


# ── Entitlements resolve to the negotiated plan ─────────────────────────────
def test_entitlements_come_from_the_assigned_plan(merchant, gold):
    services.assign_enterprise_plan(merchant, gold)
    services.activate_plan(merchant, PlanTier.ENTERPRISE)

    # API is off on every public tier — it is exactly what Enterprise re-enables.
    assert entitlements.check(merchant, "api") is True
    assert entitlements.check(merchant, "priority_support") is True
    assert entitlements.describe(merchant)["limits"]["max_cards"] is None


def test_activation_keeps_the_assigned_plan(merchant, gold):
    """activate_plan writes the *tier*; the FK must survive it or the merchant
    silently loses the deal the moment they pay for it."""
    services.assign_enterprise_plan(merchant, gold)
    services.activate_plan(merchant, PlanTier.ENTERPRISE)

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.enterprise_plan == gold
    assert sub.effective_plan() == "ENT_GOLD"


def test_an_enterprise_tier_with_no_plan_grants_nothing(merchant):
    """A half-finished assignment must fail closed, not fall back to a tier
    that has no catalogue row."""
    sub = services.subscription_for(merchant)
    sub.plan = PlanTier.ENTERPRISE
    sub.status = BillingStatus.ACTIVE
    sub.save()

    assert sub.effective_plan() == PlanTier.ENTERPRISE  # resolves to the tier...
    assert entitlements.check(merchant, "export") is False  # ...which grants nothing


def test_the_wire_reports_the_tier_not_the_internal_key(merchant, gold):
    """ "ENT_GOLD" is a catalogue key; the contract's plan enum is a fixed
    vocabulary clients switch on."""
    sub = services.assign_enterprise_plan(merchant, gold)

    assert plan_to_wire(sub) == "enterprise"


# ── Billing is the ordinary flow ────────────────────────────────────────────
def test_subscribe_bills_the_negotiated_plan_not_what_the_client_asked(merchant, gold):
    """The request body must never be able to name a price."""
    services.assign_enterprise_plan(merchant, gold)

    resp = _client(merchant).post("/api/v1/billing/subscribe", {"plan": "starter"}, format="json")

    assert resp.status_code == 200
    call = FakeGateway.calls[0]
    assert call["amount_egp"] == Decimal("7500")  # not Starter's 599
    assert call["subscription_plan_id"] == "pm-ent-30"


def test_subscribe_uses_the_negotiated_interval(merchant, gold):
    services.assign_enterprise_plan(merchant, gold, interval=BillingInterval.ANNUAL)

    _client(merchant).post("/api/v1/billing/subscribe", {"plan": "starter"}, format="json")

    call = FakeGateway.calls[0]
    assert call["amount_egp"] == Decimal("75000")
    assert call["subscription_plan_id"] == "pm-ent-360"


def test_paying_activates_them_on_the_negotiated_plan(merchant, gold):
    from billing.gateways.base import WebhookEvent

    services.assign_enterprise_plan(merchant, gold)
    _client(merchant).post("/api/v1/billing/subscribe", {"plan": "starter"}, format="json")

    services.apply_webhook_event(
        WebhookEvent(
            provider="paymob",
            kind="success",
            gateway_ref="order-ent",
            amount_egp=Decimal("7500"),
            transaction_ref="txn-ent",
        )
    )

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.status == BillingStatus.ACTIVE
    assert sub.plan == PlanTier.ENTERPRISE
    assert sub.effective_plan() == "ENT_GOLD"


def test_billing_state_shows_the_merchant_which_deal_they_are_on(merchant, gold):
    """§12.5: they see "Enterprise Gold" and its price — never the config."""
    services.assign_enterprise_plan(merchant, gold)
    services.activate_plan(merchant, PlanTier.ENTERPRISE)

    body = _client(merchant).get("/api/v1/billing").json()

    assert body["plan"] == "enterprise"
    assert body["plan_name"] == "Enterprise Gold"
    assert Decimal(body["price_egp"]) == Decimal("7500")
    assert body["billing_interval"] == "monthly"


def test_a_public_tier_reports_no_plan_name(merchant):
    services.activate_plan(merchant, PlanTier.GROWTH)

    assert _client(merchant).get("/api/v1/billing").json()["plan_name"] == ""


def test_enterprise_plans_are_not_offered_at_self_serve(merchant, gold):
    keys = {r["key"] for r in _client(merchant).get("/api/v1/billing/plans").json()}

    assert "ENT_GOLD" not in keys
    assert "ent_gold" not in keys
    assert keys == {"starter", "growth", "chain"}


def test_a_plan_someone_is_paying_for_cannot_be_deleted(merchant, gold):
    """PROTECT, not CASCADE: deleting it would take their subscription with it."""
    from django.db.models import ProtectedError

    services.assign_enterprise_plan(merchant, gold)

    with pytest.raises(ProtectedError):
        gold.delete()


# ── Enterprise must not break what reads a plan ─────────────────────────────
def test_enterprise_mrr_counts_the_negotiated_price(merchant, gold):
    """The ENTERPRISE *tier* has no catalogue row, so pricing off it returns 0 —
    every negotiated merchant would silently vanish from MRR."""
    from datetime import date, timedelta

    from console import analytics_revenue

    services.assign_enterprise_plan(merchant, gold)
    services.activate_plan(merchant, PlanTier.ENTERPRISE)

    today = date.today()
    summary = analytics_revenue.revenue_analytics(today - timedelta(days=30), today)

    assert summary["kpis"]["mrr"] == Decimal("7500")
    rows = {r["plan"]: r for r in summary["revenue_by_plan"]}
    # Broken out per deal, not collapsed into one "ENTERPRISE" bucket.
    assert rows["ENT_GOLD"]["paying_merchants"] == 1


def test_an_enterprise_merchant_can_toggle_an_automation(merchant, gold):
    gold.automations = 99
    gold.save()
    invalidate_plan_cache()
    services.assign_enterprise_plan(merchant, gold)
    services.activate_plan(merchant, PlanTier.ENTERPRISE)

    from messaging.enums import AutomationKey
    from messaging.models import Automation

    resp = _client(merchant).patch(
        f"/api/v1/automations/{AutomationKey.BIRTHDAY}", {"enabled": True}, format="json"
    )

    assert resp.status_code == 200
    assert Automation.objects.get(merchant=merchant, key=AutomationKey.BIRTHDAY).enabled is True


def test_a_half_assigned_enterprise_merchant_is_denied_not_500ed(merchant):
    """Tier set, no plan behind it — every plan lookup resolves to a key with no
    catalogue row. Each such site must fail closed; a KeyError would 500 the
    request instead of denying it."""
    from messaging.enums import AutomationKey

    sub = services.subscription_for(merchant)
    sub.plan = PlanTier.ENTERPRISE
    sub.status = BillingStatus.ACTIVE
    sub.save()

    resp = _client(merchant).patch(
        f"/api/v1/automations/{AutomationKey.BIRTHDAY}", {"enabled": True}, format="json"
    )

    assert resp.status_code == 402  # PLAN_LIMIT, not a crash
