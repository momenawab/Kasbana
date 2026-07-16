"""Subscribe creates a *recurring* subscription (plan §9.6 / phase 6).

Two things land here. Subscribing passes the Paymob plan id and the chosen
interval, so the charge sets up recurring billing instead of taking money once.
And the subscription id gets bound to a merchant — Paymob only reveals it after
3DS, and its callbacks identify us by nothing but the linking transaction.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from billing import services
from billing.gateways.base import CheckoutSession, SubscriptionEvent, WebhookEvent
from billing.models import Plan, Subscription
from billing.plans import BillingInterval, BillingStatus
from core.enums import PlanTier, Role
from tests import factories

pytestmark = pytest.mark.django_db


class FakeGateway:
    provider = "paymob"
    calls: list[dict] = []

    def create_checkout(self, **kwargs):
        FakeGateway.calls.append(kwargs)
        return CheckoutSession(checkout_url="https://pay.example/x", gateway_ref="order-1")


@pytest.fixture(autouse=True)
def gateway(monkeypatch):
    FakeGateway.calls = []
    # billing.views binds get_gateway at import time, so patching
    # billing.gateways.get_gateway would miss it once the module is loaded —
    # which is why this only shows up when the full suite runs.
    monkeypatch.setattr("billing.views.get_gateway", lambda provider="paymob": FakeGateway())
    # Ops has run create_paymob_plans for this environment.
    Plan.objects.filter(key=PlanTier.GROWTH).update(
        paymob_plan_id_monthly="pm-30", paymob_plan_id_annual="pm-360"
    )
    Plan.objects.filter(key=PlanTier.STARTER).update(paymob_plan_id_monthly="pm-st-30")
    return FakeGateway


def _client(merchant):
    from rest_framework_simplejwt.tokens import RefreshToken

    staff = factories.StaffUserFactory(merchant=merchant, role=Role.OWNER)
    client = APIClient()
    access = RefreshToken.for_user(staff.user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


# ── Subscribe wires the recurring plan ──────────────────────────────────────
def test_subscribe_attaches_the_paymob_plan(merchant):
    """Without subscription_plan_id the charge is a one-off and nothing recurs."""
    resp = _client(merchant).post("/api/v1/billing/subscribe", {"plan": "growth"}, format="json")

    assert resp.status_code == 200
    assert FakeGateway.calls[0]["subscription_plan_id"] == "pm-30"


def test_subscribe_defaults_to_monthly(merchant):
    """A client that predates the toggle must not accidentally buy a year."""
    _client(merchant).post("/api/v1/billing/subscribe", {"plan": "growth"}, format="json")

    assert FakeGateway.calls[0]["amount_egp"] == Decimal("999")
    assert Subscription.objects.get(merchant=merchant).pending_interval == (BillingInterval.MONTHLY)


def test_annual_charges_the_annual_price_and_the_annual_plan(merchant):
    _client(merchant).post(
        "/api/v1/billing/subscribe", {"plan": "growth", "interval": "annual"}, format="json"
    )

    call = FakeGateway.calls[0]
    assert call["amount_egp"] == Decimal("9990")
    assert call["subscription_plan_id"] == "pm-360"


def test_the_interval_is_recorded_before_the_webhook_arrives(merchant):
    """The renewal callback carries no interval, so if we didn't record the
    choice at checkout there'd be nothing to recover it from."""
    _client(merchant).post(
        "/api/v1/billing/subscribe", {"plan": "growth", "interval": "annual"}, format="json"
    )

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.pending_interval == BillingInterval.ANNUAL
    assert sub.status == BillingStatus.TRIALING  # access unchanged until payment


def test_an_abandoned_annual_checkout_does_not_change_what_a_monthly_sub_sees(merchant):
    """The interval stays pending until paid, exactly as pending_plan does —
    otherwise a monthly subscriber who merely *looked* at annual would see
    "9,990/yr" on their dashboard."""
    sub = services.subscription_for(merchant)
    sub.status = BillingStatus.ACTIVE
    sub.plan = PlanTier.GROWTH
    sub.billing_interval = BillingInterval.MONTHLY
    sub.save()

    _client(merchant).post(
        "/api/v1/billing/subscribe", {"plan": "growth", "interval": "annual"}, format="json"
    )
    # ...and they close the tab.

    body = _client(merchant).get("/api/v1/billing").json()
    assert body["billing_interval"] == "monthly"
    assert Decimal(body["price_egp"]) == Decimal("999")


def test_paying_applies_the_pending_interval(merchant):
    _client(merchant).post(
        "/api/v1/billing/subscribe", {"plan": "growth", "interval": "annual"}, format="json"
    )

    services.apply_webhook_event(
        WebhookEvent(
            provider="paymob",
            kind="success",
            gateway_ref="order-1",
            amount_egp=Decimal("9990"),
            transaction_ref="txn-1",
        )
    )

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.billing_interval == BillingInterval.ANNUAL
    assert sub.pending_interval == ""


def test_an_unmapped_plan_still_checks_out_as_a_one_off(merchant, caplog):
    """Before ops runs create_paymob_plans there is no plan id. Charging once
    and nudging them to re-subscribe beats taking the product offline."""
    Plan.objects.filter(key=PlanTier.CHAIN).update(paymob_plan_id_monthly="")

    resp = _client(merchant).post("/api/v1/billing/subscribe", {"plan": "chain"}, format="json")

    assert resp.status_code == 200
    assert FakeGateway.calls[0]["subscription_plan_id"] == ""
    assert "ONE-TIME charge" in caplog.text  # loud, not silent


def test_a_bad_interval_is_rejected(merchant):
    resp = _client(merchant).post(
        "/api/v1/billing/subscribe", {"plan": "growth", "interval": "weekly"}, format="json"
    )
    assert resp.status_code == 400


def test_switching_monthly_to_annual_on_the_same_plan_is_allowed(merchant):
    """Same plan + same interval is the duplicate we reject; changing the
    interval is a real re-subscribe."""
    sub = services.subscription_for(merchant)
    sub.status = BillingStatus.ACTIVE
    sub.plan = PlanTier.GROWTH
    sub.billing_interval = BillingInterval.MONTHLY
    sub.save()

    switch = _client(merchant).post(
        "/api/v1/billing/subscribe", {"plan": "growth", "interval": "annual"}, format="json"
    )
    duplicate = _client(merchant).post(
        "/api/v1/billing/subscribe", {"plan": "growth", "interval": "monthly"}, format="json"
    )

    assert switch.status_code == 200
    assert duplicate.status_code == 409


# ── GET /billing reports the interval ───────────────────────────────────────
def test_billing_state_reports_the_interval_and_matching_price(merchant):
    sub = services.subscription_for(merchant)
    sub.status = BillingStatus.ACTIVE
    sub.plan = PlanTier.GROWTH
    sub.billing_interval = BillingInterval.ANNUAL
    sub.save()

    body = _client(merchant).get("/api/v1/billing").json()

    # 999 here would read as "999/yr" — the dashboard cannot disambiguate
    # price_egp without the interval beside it.
    assert body["billing_interval"] == "annual"
    assert Decimal(body["price_egp"]) == Decimal("9990")


# ── Binding the Paymob subscription to a merchant ───────────────────────────
def _linked(merchant, transaction_ref="txn-77"):
    sub = services.subscription_for(merchant)
    sub.provider = "paymob"
    sub.gateway_ref = "order-1"
    sub.linking_transaction_ref = transaction_ref
    sub.plan = PlanTier.GROWTH
    sub.save()
    return sub


def _event(trigger="Subscription Created", sub_id="1264", initial="txn-77", **kw):
    return SubscriptionEvent(
        provider="paymob",
        trigger_type=trigger,
        subscription_id=sub_id,
        initial_transaction=initial,
        **kw,
    )


def test_the_transaction_webhook_records_the_linking_transaction(merchant):
    """The subscription callbacks carry only this id to identify us by."""
    services.begin_checkout(merchant, plan="GROWTH", provider="paymob", gateway_ref="order-1")

    services.apply_webhook_event(
        WebhookEvent(
            provider="paymob",
            kind="success",
            gateway_ref="order-1",
            amount_egp=Decimal("1"),
            transaction_ref="txn-77",
        )
    )

    assert Subscription.objects.get(merchant=merchant).linking_transaction_ref == "txn-77"


def test_subscription_created_binds_the_id_to_the_merchant(merchant):
    _linked(merchant)

    sub = services.apply_subscription_event(_event())

    assert sub is not None
    assert Subscription.objects.get(merchant=merchant).paymob_subscription_id == "1264"


def test_binding_heals_if_the_created_callback_was_missed(merchant):
    """Paymob promises no ordering between the transaction and subscription
    webhooks (§10). If the first callback couldn't bind, a later one must."""
    _linked(merchant)

    renewal = _event(trigger="Successful Transaction", amount_egp=Decimal("999"))
    sub = services.apply_subscription_event(renewal)

    assert sub is not None
    assert Subscription.objects.get(merchant=merchant).paymob_subscription_id == "1264"
    assert Subscription.objects.get(merchant=merchant).status == BillingStatus.ACTIVE


def test_an_already_bound_subscription_is_matched_by_id_not_rebound(merchant):
    sub = _linked(merchant)
    sub.paymob_subscription_id = "1264"
    sub.save()

    services.apply_subscription_event(_event(trigger="resumed"))

    assert Subscription.objects.get(merchant=merchant).paymob_subscription_id == "1264"


def test_a_second_subscription_on_the_same_charge_does_not_steal_the_binding(merchant, caplog):
    """Rebinding would orphan the first subscription — and leave it billing,
    since we'd no longer hold the id needed to suspend it."""
    sub = _linked(merchant)
    sub.paymob_subscription_id = "1264"
    sub.save()

    result = services.apply_subscription_event(_event(sub_id="9999"))

    assert result is None
    assert Subscription.objects.get(merchant=merchant).paymob_subscription_id == "1264"
    assert "not rebinding" in caplog.text


def test_an_unknown_linking_transaction_does_not_match(merchant):
    _linked(merchant, transaction_ref="txn-77")

    assert services.apply_subscription_event(_event(initial="txn-other")) is None


def test_a_callback_without_an_initial_transaction_cannot_bind(merchant):
    _linked(merchant)

    assert services.apply_subscription_event(_event(initial="")) is None
