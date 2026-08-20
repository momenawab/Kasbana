"""Paymob Subscription Plan creation — adapter + `create_paymob_plans` command.

The request shape is pinned against Paymob's published contract (docs verified
2026-07-16): several of these fields are easy to get subtly wrong and only fail
against the live API, where the blast radius is real plans on a real account.
No network: httpx is driven through a MockTransport so the real request-building
code runs.
"""

from __future__ import annotations

import json
from decimal import Decimal
from io import StringIO

import httpx
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from billing.gateways.paymob import PaymobGateway
from billing.models import Plan
from billing.plans import BillingInterval
from core.enums import PlanTier

pytestmark = pytest.mark.django_db


LIVE_CFG = {
    "PAYMOB": {
        "API_KEY": "test-api-key",
        "HMAC_SECRET": "test-hmac",
        "SECRET_KEY": "test-secret",
        "PUBLIC_KEY": "test-public",
        "CARD_INTEGRATION_ID": "111",
        "MOTO_INTEGRATION_ID": "999",
    }
}


def _mock_paymob(monkeypatch, handler):
    """Route the adapter's httpx calls to ``handler`` instead of the network."""
    real_client = httpx.Client

    def factory(*args, **kwargs):
        kwargs.pop("timeout", None)
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("billing.gateways.paymob.httpx.Client", factory)


def _recording_handler(seen: list[httpx.Request], plan_id: int = 1186):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/api/auth/tokens":
            return httpx.Response(201, json={"token": "auth-token-xyz"})
        if request.url.path == "/api/acceptance/subscription-plans":
            return httpx.Response(201, json={"id": plan_id, "name": "x", "frequency": 30})
        return httpx.Response(404, json={"detail": "unexpected"})

    return handler


# ── adapter: create_subscription_plan ───────────────────────────────────────
def test_rejects_a_frequency_paymob_does_not_accept(settings):
    """Paymob's frequency is a closed enum; catching it here beats a 400 from
    the live API mid-way through creating a set of plans."""
    settings.BILLING = LIVE_CFG
    with pytest.raises(ValueError, match="not one of Paymob's"):
        PaymobGateway().create_subscription_plan(
            name="Monthly", amount_egp=Decimal("999"), frequency=31, webhook_url="https://x/y"
        )


def test_stub_mode_makes_no_network_call(settings):
    settings.BILLING = {"PAYMOB": {}}
    got = PaymobGateway().create_subscription_plan(
        name="Stampn Growth", amount_egp=Decimal("999"), frequency=30, webhook_url="https://x/y"
    )
    assert got == "paymob-stub-plan-30-stampn-growth"


def test_refuses_to_build_a_plan_without_the_moto_integration(settings):
    """A plan on the 3DS card integration can never auto-deduct — every renewal
    would demand an authentication nobody is there to give."""
    settings.BILLING = {"PAYMOB": {**LIVE_CFG["PAYMOB"], "MOTO_INTEGRATION_ID": ""}}
    with pytest.raises(ValueError, match="MOTO_INTEGRATION_ID"):
        PaymobGateway().create_subscription_plan(
            name="Growth", amount_egp=Decimal("999"), frequency=30, webhook_url="https://x/y"
        )


def test_sends_the_documented_request_shape(settings, monkeypatch):
    settings.BILLING = LIVE_CFG
    seen: list[httpx.Request] = []
    _mock_paymob(monkeypatch, _recording_handler(seen))

    got = PaymobGateway().create_subscription_plan(
        name="Stampn Growth (annual)",
        amount_egp=Decimal("9990"),
        frequency=360,
        webhook_url="https://api.example.com/api/v1/billing/webhook/paymob/subscription",
        retrial_days="3",
    )

    assert got == "1186"  # Paymob returns a number; we store a string
    create = seen[-1]
    assert str(create.url) == "https://accept.paymob.com/api/acceptance/subscription-plans"
    body = json.loads(create.content)

    # Paymob's field is `integration` and it is a number. `integration_id` —
    # the name the transaction APIs use — is silently ignored here.
    assert body["integration"] == 999
    assert "integration_id" not in body
    assert body["frequency"] == 360
    assert body["amount_cents"] == 999000
    assert body["plan_type"] == "rent"
    assert body["retrial_days"] == "3"
    # Must stay false: it keeps a discounted/1 EGP first charge from becoming
    # the renewal price, and Paymob only honours subscription_start_date when
    # it is false — which is what defers the day-14 trial charge.
    assert body["use_transaction_amount"] is False


def test_authenticates_with_the_legacy_auth_token_not_the_secret_key(settings, monkeypatch):
    """Plan creation takes a Bearer token minted from API_KEY via
    api/auth/tokens — passing SECRET_KEY here 401s."""
    settings.BILLING = LIVE_CFG
    seen: list[httpx.Request] = []
    _mock_paymob(monkeypatch, _recording_handler(seen))

    PaymobGateway().create_subscription_plan(
        name="Growth", amount_egp=Decimal("999"), frequency=30, webhook_url="https://x/y"
    )

    auth, create = seen[0], seen[1]
    assert auth.url.path == "/api/auth/tokens"
    assert json.loads(auth.content) == {"api_key": "test-api-key"}
    assert create.headers["Authorization"] == "Bearer auth-token-xyz"


def test_omits_optional_fields_when_unset(settings, monkeypatch):
    """Paymob defaults reminder/retrial itself; sending "" is not the same as
    omitting them."""
    settings.BILLING = LIVE_CFG
    seen: list[httpx.Request] = []
    _mock_paymob(monkeypatch, _recording_handler(seen))

    PaymobGateway().create_subscription_plan(
        name="Growth", amount_egp=Decimal("999"), frequency=30, webhook_url="https://x/y"
    )
    body = json.loads(seen[-1].content)
    assert "retrial_days" not in body
    assert "reminder_days" not in body


# ── management command ──────────────────────────────────────────────────────
def _run(**kwargs) -> str:
    out = StringIO()
    call_command("create_paymob_plans", stdout=out, **kwargs)
    return out.getvalue()


def test_dry_run_touches_nothing(settings, monkeypatch):
    settings.BILLING = LIVE_CFG
    settings.BASE_URL = "https://api.example.com"
    seen: list[httpx.Request] = []
    _mock_paymob(monkeypatch, _recording_handler(seen))

    out = _run(dry_run=True)

    assert seen == []  # no Paymob calls
    assert not Plan.objects.exclude(paymob_plan_id_monthly="").exists()
    assert "would create" in out


def test_creates_one_plan_per_sellable_tier_and_interval(settings, monkeypatch):
    settings.BILLING = LIVE_CFG
    settings.BASE_URL = "https://api.example.com"
    counter = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/tokens":
            return httpx.Response(201, json={"token": "t"})
        counter["n"] += 1
        return httpx.Response(201, json={"id": 1000 + counter["n"]})

    _mock_paymob(monkeypatch, handler)
    _run()

    # Starter/Growth/Chain x monthly/annual; FREE is not public and is 0-priced.
    assert counter["n"] == 6
    growth = Plan.objects.get(key=PlanTier.GROWTH)
    assert growth.paymob_plan_id(BillingInterval.MONTHLY)
    assert growth.paymob_plan_id(BillingInterval.ANNUAL)
    assert growth.paymob_plan_id(BillingInterval.MONTHLY) != growth.paymob_plan_id(
        BillingInterval.ANNUAL
    )
    assert Plan.objects.get(key=PlanTier.FREE).paymob_plan_id(BillingInterval.MONTHLY) == ""


def test_rerun_skips_already_mapped_tiers(settings, monkeypatch):
    """Paymob has no get-or-create: a second unguarded run would duplicate every
    live plan and orphan the ids we already stored."""
    settings.BILLING = LIVE_CFG
    settings.BASE_URL = "https://api.example.com"
    seen: list[httpx.Request] = []
    _mock_paymob(monkeypatch, _recording_handler(seen))
    Plan.objects.filter(is_public=True).update(
        paymob_plan_id_monthly="pre-1", paymob_plan_id_annual="pre-2"
    )

    out = _run()

    assert seen == []
    assert "already mapped" in out
    assert Plan.objects.get(key=PlanTier.GROWTH).paymob_plan_id_monthly == "pre-1"


def test_force_recreates_mapped_tiers(settings, monkeypatch):
    settings.BILLING = LIVE_CFG
    settings.BASE_URL = "https://api.example.com"
    _mock_paymob(monkeypatch, _recording_handler([], plan_id=777))
    Plan.objects.filter(is_public=True).update(paymob_plan_id_monthly="stale")

    _run(force=True)

    assert Plan.objects.get(key=PlanTier.GROWTH).paymob_plan_id_monthly == "777"


def test_refuses_a_non_https_webhook_url(settings, monkeypatch):
    """Paymob calls the webhook from the outside world; a localhost URL yields
    plans whose renewals we would never hear about."""
    settings.BILLING = LIVE_CFG
    settings.BASE_URL = "http://localhost:8000"
    _mock_paymob(monkeypatch, _recording_handler([]))

    with pytest.raises(CommandError, match="non-HTTPS"):
        _run()


def test_webhook_url_is_registered_on_every_plan(settings, monkeypatch):
    """Subscription-level events only arrive if each plan carries the URL."""
    settings.BILLING = LIVE_CFG
    settings.BASE_URL = "https://api.example.com"
    seen: list[httpx.Request] = []
    _mock_paymob(monkeypatch, _recording_handler(seen))

    _run()

    creates = [r for r in seen if r.url.path == "/api/acceptance/subscription-plans"]
    assert creates
    for req in creates:
        assert (
            json.loads(req.content)["webhook_url"]
            == "https://api.example.com/api/v1/billing/webhook/paymob/subscription"
        )
