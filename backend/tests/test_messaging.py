"""Tests for messaging / Engage (Phase 1.7).

WhatsApp send + metering + quota gating, the one-off customer message endpoint,
campaigns (create/send/schedule), segments, and automations (toggle + count
gating). Celery runs eagerly in dev settings, so ``.delay`` executes inline and
metering increments are observable.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from billing.services import activate_plan
from core.enums import PlanTier, Role
from messaging import metering
from messaging.enums import AutomationKey, MessageChannel
from messaging.models import Automation, Campaign, WhatsAppUsage, current_period
from tests import factories

pytestmark = pytest.mark.django_db


def _client_for(role, merchant):
    from rest_framework_simplejwt.tokens import RefreshToken

    staff = factories.StaffUserFactory(merchant=merchant, role=role)
    client = APIClient()
    access = RefreshToken.for_user(staff.user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client, staff


@pytest.fixture
def paid_merchant():
    """A merchant on the Growth plan (WhatsApp enabled, quota 2000)."""
    m = factories.MerchantFactory()
    activate_plan(m, PlanTier.GROWTH)
    return m


# ── metering ──────────────────────────────────────────────────────────────────
def test_quota_and_usage(paid_merchant):
    assert metering.quota_for(paid_merchant) == 2000
    assert metering.used_this_period(paid_merchant) == 0
    metering.record_send(paid_merchant, count=3)
    assert metering.used_this_period(paid_merchant) == 3


def test_ensure_quota_raises_when_exhausted(paid_merchant):
    from common.errors import PlanLimit

    metering.record_send(paid_merchant, count=2000)
    with pytest.raises(PlanLimit):
        metering.ensure_quota(paid_merchant, count=1)


def test_send_whatsapp_task_meters(paid_merchant):
    from messaging.tasks import send_whatsapp

    customer = factories.CustomerCardFactory(merchant=paid_merchant)
    send_whatsapp(str(customer.id), "hello")  # run directly
    assert metering.used_this_period(paid_merchant) == 1


# ── one-off customer message ──────────────────────────────────────────────────
def test_customer_message_whatsapp_sends_and_meters(paid_merchant):
    client, _ = _client_for(Role.ADMIN, paid_merchant)
    customer = factories.CustomerCardFactory(merchant=paid_merchant)
    resp = client.post(
        f"/api/v1/customers/{customer.id}/message",
        {"channel": "WHATSAPP", "text": "your reward is ready"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert WhatsAppUsage.objects.get(merchant=paid_merchant, period=current_period()).sent == 1


def test_customer_message_whatsapp_blocked_when_capability_off(merchant):
    # FREE-level/trial merchant... trial actually has whatsapp on (Growth-level).
    # Force a locked merchant: cancel so effective_plan is None.
    from billing.services import lock

    lock(merchant)
    client, _ = _client_for(Role.ADMIN, merchant)
    customer = factories.CustomerCardFactory(merchant=merchant)
    resp = client.post(
        f"/api/v1/customers/{customer.id}/message",
        {"channel": "WHATSAPP", "text": "hi"},
        format="json",
    )
    assert resp.status_code == 402


def test_customer_message_quota_exhausted_returns_402(paid_merchant):
    metering.record_send(paid_merchant, count=2000)
    client, _ = _client_for(Role.ADMIN, paid_merchant)
    customer = factories.CustomerCardFactory(merchant=paid_merchant)
    resp = client.post(
        f"/api/v1/customers/{customer.id}/message",
        {"channel": "WHATSAPP", "text": "hi"},
        format="json",
    )
    assert resp.status_code == 402


def test_customer_message_push_ok(paid_merchant):
    from wallets.models import WalletMessage

    client, _ = _client_for(Role.ADMIN, paid_merchant)
    customer = factories.CustomerCardFactory(merchant=paid_merchant)
    resp = client.post(
        f"/api/v1/customers/{customer.id}/message",
        {"channel": "PUSH", "text": "hi"},
        format="json",
    )
    assert resp.status_code == 200
    # PUSH does not touch the WhatsApp counter (free channel).
    assert metering.used_this_period(paid_merchant) == 0
    # The message is persisted so the Apple pass can render it.
    msg = WalletMessage.objects.get(customer_card=customer)
    assert msg.body == "hi"


def test_customer_message_both_sends_whatsapp_and_push(paid_merchant):
    from wallets.models import WalletMessage

    client, _ = _client_for(Role.ADMIN, paid_merchant)
    customer = factories.CustomerCardFactory(merchant=paid_merchant)
    resp = client.post(
        f"/api/v1/customers/{customer.id}/message",
        {"channel": "BOTH", "text": "combo"},
        format="json",
    )
    assert resp.status_code == 200
    assert metering.used_this_period(paid_merchant) == 1  # WhatsApp metered
    assert WalletMessage.objects.filter(customer_card=customer, body="combo").exists()  # + push


# ── campaigns ─────────────────────────────────────────────────────────────────
def test_create_campaign_sends_immediately(paid_merchant):
    client, _ = _client_for(Role.ADMIN, paid_merchant)
    factories.CustomerCardFactory(merchant=paid_merchant)
    resp = client.post(
        "/api/v1/campaigns",
        {"channel": "WHATSAPP", "audience": "all", "message": "promo"},
        format="json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "sent"
    assert body["stats"]["delivered"] == 1
    # One WhatsApp recipient → one metered send.
    assert metering.used_this_period(paid_merchant) == 1


def test_create_campaign_scheduled(paid_merchant):
    from datetime import timedelta

    from django.utils import timezone

    client, _ = _client_for(Role.ADMIN, paid_merchant)
    factories.CustomerCardFactory(merchant=paid_merchant)
    future = (timezone.now() + timedelta(days=1)).isoformat()
    resp = client.post(
        "/api/v1/campaigns",
        {"channel": "PUSH", "audience": "all", "message": "later", "schedule_at": future},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "scheduled"
    assert metering.used_this_period(paid_merchant) == 0


def test_campaign_list_tenant_scoped(paid_merchant):
    other = factories.MerchantFactory()
    Campaign.objects.create(
        merchant=paid_merchant, channel=MessageChannel.PUSH, audience="all", message="a"
    )
    Campaign.objects.create(
        merchant=other, channel=MessageChannel.PUSH, audience="all", message="b"
    )
    client, _ = _client_for(Role.ADMIN, paid_merchant)
    resp = client.get("/api/v1/campaigns")
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 1


def test_campaign_whatsapp_quota_gate(paid_merchant):
    metering.record_send(paid_merchant, count=2000)
    factories.CustomerCardFactory(merchant=paid_merchant)
    client, _ = _client_for(Role.ADMIN, paid_merchant)
    resp = client.post(
        "/api/v1/campaigns",
        {"channel": "WHATSAPP", "audience": "all", "message": "promo"},
        format="json",
    )
    assert resp.status_code == 402


# ── segments ──────────────────────────────────────────────────────────────────
def test_segments_listing(paid_merchant, no_cooldown):
    from core import ledger

    card = factories.CardFactory(merchant=paid_merchant, stamps_required=2)
    ready = factories.CustomerCardFactory(card=card, merchant=paid_merchant)
    ledger.add_stamp(ready)
    ledger.add_stamp(ready)  # now reward_ready
    factories.CustomerCardFactory(merchant=paid_merchant)

    client, _ = _client_for(Role.ADMIN, paid_merchant)
    resp = client.get("/api/v1/segments")
    assert resp.status_code == 200
    by_key = {s["key"]: s for s in resp.json()["results"]}
    assert by_key["all"]["count"] == 2
    assert by_key["reward_ready"]["count"] == 1


# ── automations ───────────────────────────────────────────────────────────────
def test_automations_list_defaults(paid_merchant):
    client, _ = _client_for(Role.ADMIN, paid_merchant)
    resp = client.get("/api/v1/automations")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert {r["key"] for r in results} == set(AutomationKey.values)
    assert all(r["enabled"] is False for r in results)


def test_automation_toggle(paid_merchant):
    client, _ = _client_for(Role.ADMIN, paid_merchant)
    resp = client.patch(
        "/api/v1/automations/birthday",
        {"enabled": True, "channel": "WHATSAPP", "template": "hbd!"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True
    assert Automation.objects.get(merchant=paid_merchant, key="birthday").enabled is True


def test_automation_count_gated(merchant):
    # FREE plan allows 0 automations; force the merchant onto FREE (active).
    activate_plan(merchant, PlanTier.FREE)
    client, _ = _client_for(Role.ADMIN, merchant)
    resp = client.patch("/api/v1/automations/birthday", {"enabled": True}, format="json")
    assert resp.status_code == 402


def test_automation_unknown_key_422(paid_merchant):
    client, _ = _client_for(Role.ADMIN, paid_merchant)
    resp = client.patch("/api/v1/automations/bogus", {"enabled": True}, format="json")
    assert resp.status_code == 422


# ── automation triggers ───────────────────────────────────────────────────────
def test_reward_ready_automation_fires_on_stamp(paid_merchant, no_cooldown):
    Automation.objects.create(
        merchant=paid_merchant,
        key=AutomationKey.REWARD_READY,
        enabled=True,
        channel=MessageChannel.WHATSAPP,
        template="ready!",
    )
    card = factories.CardFactory(merchant=paid_merchant, stamps_required=1)
    customer = factories.CustomerCardFactory(card=card, merchant=paid_merchant)

    client, _ = _client_for(Role.SCANNER, paid_merchant)
    resp = client.post(
        "/api/v1/loyalty/stamp",
        {"customer_card_id": str(customer.id), "delta": 1},
        format="json",
    )
    assert resp.status_code == 200
    # The reward-ready trigger enqueued (eager) a WhatsApp send → metered.
    assert metering.used_this_period(paid_merchant) == 1


def test_push_automation_fires_free_on_stamp(merchant, no_cooldown):
    """A PUSH-channel automation reaches the customer via the free wallet channel
    — no WhatsApp capability or quota required (works on a non-paid merchant)."""
    from wallets.models import WalletMessage

    Automation.objects.create(
        merchant=merchant,
        key=AutomationKey.REWARD_READY,
        enabled=True,
        channel=MessageChannel.PUSH,
        template="Your reward is ready!",
    )
    card = factories.CardFactory(merchant=merchant, stamps_required=1)
    customer = factories.CustomerCardFactory(card=card, merchant=merchant)

    client, _ = _client_for(Role.SCANNER, merchant)
    resp = client.post(
        "/api/v1/loyalty/stamp",
        {"customer_card_id": str(customer.id), "delta": 1},
        format="json",
    )
    assert resp.status_code == 200
    # Delivered as a wallet message, nothing metered against WhatsApp.
    assert WalletMessage.objects.filter(
        customer_card=customer, body="Your reward is ready!"
    ).exists()
    assert metering.used_this_period(merchant) == 0


def test_daily_scan_fires_birthday(paid_merchant):
    from datetime import date

    from messaging.automation import run_daily_scan

    Automation.objects.create(
        merchant=paid_merchant,
        key=AutomationKey.BIRTHDAY,
        enabled=True,
        channel=MessageChannel.WHATSAPP,
        template="hbd",
    )
    today = date(2026, 6, 29)
    factories.CustomerCardFactory(merchant=paid_merchant, birthday=date(1990, 6, 29))
    factories.CustomerCardFactory(merchant=paid_merchant, birthday=date(1990, 1, 1))

    fired = run_daily_scan(today)
    assert fired == 1
