"""Paymob adapter — Intention checkout, subscription actions, subscription HMAC.

Pins the wire contract for the recurring flow (docs verified 2026-07-16). The
two auth schemes and the two HMAC formulas are the easy things to get wrong
here, and both only fail against the live gateway, so they're asserted directly.
No network: httpx runs through a MockTransport.
"""

from __future__ import annotations

import hashlib
import hmac as hmac_lib
import json
from decimal import Decimal

import httpx
import pytest

from billing.gateways.base import WebhookVerificationError
from billing.gateways.paymob import PaymobGateway

pytestmark = pytest.mark.django_db

SECRET = "test-hmac-secret"

LIVE_CFG = {
    "PAYMOB": {
        "API_KEY": "test-api-key",
        "HMAC_SECRET": SECRET,
        "SECRET_KEY": "sk_test_123",
        "PUBLIC_KEY": "pk_test_456",
        "CARD_INTEGRATION_ID": "111",
        "MOTO_INTEGRATION_ID": "999",
    }
}

INTENTION_RESPONSE = {
    "id": "int_abc",
    "client_secret": "cs_live_xyz",
    "intention_order_id": 5551234,
}


def _mock(monkeypatch, handler):
    real_client = httpx.Client

    def factory(*args, **kwargs):
        kwargs.pop("timeout", None)
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("billing.gateways.paymob.httpx.Client", factory)


def _handler(seen: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/api/auth/tokens":
            return httpx.Response(201, json={"token": "auth-token-xyz"})
        if request.url.path == "/v1/intention/":
            return httpx.Response(201, json=INTENTION_RESPONSE)
        if "/subscriptions/" in request.url.path:
            return httpx.Response(200, json={"id": 1264, "state": "suspended"})
        return httpx.Response(404, json={"detail": "unexpected"})

    return handler


def _sub_hmac(trigger_type: str, subscription_id: str | int) -> str:
    return hmac_lib.new(
        SECRET.encode(), f"{trigger_type}for{subscription_id}".encode(), hashlib.sha512
    ).hexdigest()


def _callback(trigger_type="suspended", sub_id=1264, **data) -> bytes:
    payload = {
        "paymob_request_id": "df9e4ecf",
        "subscription_data": {"id": sub_id, **data},
        "trigger_type": trigger_type,
        "hmac": _sub_hmac(trigger_type, sub_id),
    }
    return json.dumps(payload).encode()


# ── Intention checkout ──────────────────────────────────────────────────────
def test_stub_mode_without_a_secret_key(settings):
    settings.BILLING = {"PAYMOB": {}}
    session = PaymobGateway().create_checkout(
        merchant_id="m1", plan="GROWTH", amount_egp=Decimal("999")
    )
    assert session.gateway_ref == "paymob-stub-m1-GROWTH"
    assert "accept.paymob.com" not in session.checkout_url


def test_checkout_uses_the_intention_api_with_token_auth(settings, monkeypatch):
    """The Intention API wants the secret key prefixed with "Token". A Bearer
    auth-token — what the subscription endpoints take — is rejected here."""
    settings.BILLING = LIVE_CFG
    seen: list[httpx.Request] = []
    _mock(monkeypatch, _handler(seen))

    PaymobGateway().create_checkout(merchant_id="m1", plan="GROWTH", amount_egp=Decimal("999"))

    req = seen[-1]
    assert str(req.url) == "https://accept.paymob.com/v1/intention/"
    assert req.headers["Authorization"] == "Token sk_test_123"
    # No legacy order/payment_key round-trip any more.
    assert not any(r.url.path == "/api/ecommerce/orders" for r in seen)


def test_checkout_returns_a_unified_checkout_url(settings, monkeypatch):
    settings.BILLING = LIVE_CFG
    _mock(monkeypatch, _handler([]))

    session = PaymobGateway().create_checkout(
        merchant_id="m1", plan="GROWTH", amount_egp=Decimal("999")
    )

    assert session.checkout_url == (
        "https://accept.paymob.com/unifiedcheckout/?publicKey=pk_test_456&clientSecret=cs_live_xyz"
    )
    # The order id, not the intention id: the transaction callback carries it as
    # order.id, which is how a webhook is matched back to a merchant.
    assert session.gateway_ref == "5551234"


def test_checkout_body_matches_the_documented_shape(settings, monkeypatch):
    settings.BILLING = LIVE_CFG
    seen: list[httpx.Request] = []
    _mock(monkeypatch, _handler(seen))

    PaymobGateway().create_checkout(
        merchant_id="m1", plan="GROWTH", amount_egp=Decimal("999"), customer_email="a@b.com"
    )

    body = json.loads(seen[-1].content)
    assert body["amount"] == 99900
    assert body["currency"] == "EGP"
    # The 3DS card integration — the customer must be present to authenticate,
    # which is what saves the card. Moto here would break card-linking.
    assert body["payment_methods"] == [111]
    assert body["items"][0]["amount"] == 99900  # required by the API
    assert body["billing_data"]["phone_number"]  # required by the API
    assert body["billing_data"]["email"] == "a@b.com"
    assert body["extras"] == {"merchant_id": "m1", "plan": "GROWTH"}


def test_subscription_fields_are_omitted_for_a_plain_checkout(settings, monkeypatch):
    settings.BILLING = LIVE_CFG
    seen: list[httpx.Request] = []
    _mock(monkeypatch, _handler(seen))

    PaymobGateway().create_checkout(merchant_id="m1", plan="GROWTH", amount_egp=Decimal("999"))

    body = json.loads(seen[-1].content)
    assert "subscription_plan_id" not in body
    assert "subscription_start_date" not in body


def test_card_upfront_trial_defers_the_first_deduction(settings, monkeypatch):
    """The 1 EGP charge links the card now; the plan price is taken at day 14."""
    settings.BILLING = LIVE_CFG
    seen: list[httpx.Request] = []
    _mock(monkeypatch, _handler(seen))

    PaymobGateway().create_checkout(
        merchant_id="m1",
        plan="STARTER",
        amount_egp=Decimal("1"),
        subscription_plan_id="1186",
        subscription_start_date="2026-07-30",
    )

    body = json.loads(seen[-1].content)
    assert body["amount"] == 100  # 1 EGP verification charge, not the plan price
    assert body["subscription_plan_id"] == 1186  # a number, per the API
    assert body["subscription_start_date"] == "2026-07-30"


# ── Subscription actions ────────────────────────────────────────────────────
@pytest.mark.parametrize("action", ["suspend", "resume", "cancel"])
def test_subscription_actions_hit_the_documented_endpoint(settings, monkeypatch, action):
    settings.BILLING = LIVE_CFG
    seen: list[httpx.Request] = []
    _mock(monkeypatch, _handler(seen))

    getattr(PaymobGateway(), f"{action}_subscription")("1264")

    req = seen[-1]
    assert req.method == "POST"
    assert req.url.path == f"/api/acceptance/subscriptions/1264/{action}"
    # These take the Bearer auth-token, not the Intention API's secret key.
    assert req.headers["Authorization"] == "Bearer auth-token-xyz"


def test_action_without_a_subscription_id_raises(settings):
    """A blank id would POST to .../subscriptions//suspend and silently 404 —
    i.e. we'd think we stopped billing someone when we hadn't."""
    settings.BILLING = LIVE_CFG
    with pytest.raises(ValueError, match="without a Paymob subscription id"):
        PaymobGateway().suspend_subscription("")


def test_actions_stub_out_without_credentials(settings):
    settings.BILLING = {"PAYMOB": {}}
    assert PaymobGateway().cancel_subscription("1264")["stub"] is True


# ── Subscription callback HMAC ──────────────────────────────────────────────
def test_verifies_and_parses_a_subscription_callback(settings):
    settings.BILLING = LIVE_CFG
    event = PaymobGateway().verify_and_parse_subscription_event(
        headers={},
        body=_callback(
            trigger_type="Successful Transaction",
            sub_id=1264,
            amount_cents=99900,
            plan_id=1186,
            state="active",
            next_billing="2026-08-15",
        ),
    )
    assert event.trigger_type == "Successful Transaction"
    assert event.subscription_id == "1264"
    assert event.amount_egp == Decimal("999")
    assert event.plan_id == "1186"
    assert event.next_billing == "2026-08-15"


def test_hmac_matches_paymob_documented_example(settings):
    """Paymob's own worked example: trigger "suspended" + id 1264 signs the
    string "suspendedfor1264"."""
    settings.BILLING = LIVE_CFG
    expected = hmac_lib.new(SECRET.encode(), b"suspendedfor1264", hashlib.sha512).hexdigest()
    event = PaymobGateway().verify_and_parse_subscription_event(
        headers={},
        body=json.dumps(
            {
                "subscription_data": {"id": 1264},
                "trigger_type": "suspended",
                "hmac": expected,
            }
        ).encode(),
    )
    assert event.subscription_id == "1264"


def test_rejects_a_forged_subscription_callback(settings):
    settings.BILLING = LIVE_CFG
    body = json.loads(_callback(trigger_type="canceled", sub_id=1264))
    body["hmac"] = "0" * 128
    with pytest.raises(WebhookVerificationError, match="subscription HMAC"):
        PaymobGateway().verify_and_parse_subscription_event(
            headers={}, body=json.dumps(body).encode()
        )


def test_a_replayed_hmac_does_not_transfer_between_triggers(settings):
    """The signature covers the trigger, so a "resumed" digest can't be
    replayed to fake a "canceled" for the same subscription."""
    settings.BILLING = LIVE_CFG
    body = {
        "subscription_data": {"id": 1264},
        "trigger_type": "canceled",
        "hmac": _sub_hmac("resumed", 1264),
    }
    with pytest.raises(WebhookVerificationError):
        PaymobGateway().verify_and_parse_subscription_event(
            headers={}, body=json.dumps(body).encode()
        )


def test_unknown_trigger_types_still_parse(settings):
    """Paymob can add triggers without telling us; an unrecognised one must
    reach the service layer to be logged, not blow up in the adapter."""
    settings.BILLING = LIVE_CFG
    event = PaymobGateway().verify_and_parse_subscription_event(
        headers={}, body=_callback(trigger_type="some_future_trigger", sub_id=7)
    )
    assert event.trigger_type == "some_future_trigger"
    assert event.subscription_id == "7"


def test_missing_hmac_secret_is_fatal_outside_debug(settings):
    settings.BILLING = {"PAYMOB": {**LIVE_CFG["PAYMOB"], "HMAC_SECRET": ""}}
    settings.DEBUG = False
    with pytest.raises(WebhookVerificationError, match="not configured"):
        PaymobGateway().verify_and_parse_subscription_event(headers={}, body=_callback())
