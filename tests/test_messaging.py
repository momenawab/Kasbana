"""Tests for messaging / Engage (Phase 1.7).

The one-off customer message endpoint, campaigns (create/send/schedule),
segments, and automations (toggle + count gating). Delivery is the free wallet
push channel; Celery runs eagerly in dev settings, so ``.delay`` executes inline.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from billing.services import activate_plan
from core.enums import PlanTier, Role
from messaging.enums import AutomationKey
from messaging.models import Automation, Campaign
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
    """A merchant active on the Growth plan."""
    m = factories.MerchantFactory()
    activate_plan(m, PlanTier.GROWTH)
    return m


# ── one-off customer message ──────────────────────────────────────────────────
def test_customer_message_push_ok(paid_merchant):
    from wallets.models import WalletMessage

    client, _ = _client_for(Role.ADMIN, paid_merchant)
    customer = factories.CustomerCardFactory(merchant=paid_merchant)
    resp = client.post(
        f"/api/v1/customers/{customer.id}/message",
        {"text": "hi"},
        format="json",
    )
    assert resp.status_code == 200
    # The message is persisted so the Apple pass can render it.
    msg = WalletMessage.objects.get(customer_card=customer)
    assert msg.body == "hi"


# ── campaigns ─────────────────────────────────────────────────────────────────
def test_create_campaign_sends_immediately(paid_merchant):
    from wallets.models import WalletMessage

    client, _ = _client_for(Role.ADMIN, paid_merchant)
    customer = factories.CustomerCardFactory(merchant=paid_merchant)
    resp = client.post(
        "/api/v1/campaigns",
        {"audience": "all", "message": "promo"},
        format="json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "sent"
    assert body["stats"]["delivered"] == 1
    # Free wallet channel: a message is pushed to the recipient.
    assert WalletMessage.objects.filter(customer_card=customer, body="promo").exists()


def test_create_campaign_scheduled(paid_merchant):
    from datetime import timedelta

    from django.utils import timezone

    client, _ = _client_for(Role.ADMIN, paid_merchant)
    factories.CustomerCardFactory(merchant=paid_merchant)
    future = (timezone.now() + timedelta(days=1)).isoformat()
    resp = client.post(
        "/api/v1/campaigns",
        {"audience": "all", "message": "later", "schedule_at": future},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "scheduled"


def test_send_due_campaigns_dispatches_only_past_due(paid_merchant):
    from datetime import timedelta

    from django.utils import timezone

    from messaging.enums import CampaignStatus
    from messaging.tasks import send_due_campaigns
    from wallets.models import WalletMessage

    customer = factories.CustomerCardFactory(merchant=paid_merchant)
    now = timezone.now()
    due = Campaign.objects.create(
        merchant=paid_merchant,
        audience="all",
        message="now",
        status=CampaignStatus.SCHEDULED,
        schedule_at=now - timedelta(minutes=1),
    )
    future = Campaign.objects.create(
        merchant=paid_merchant,
        audience="all",
        message="later",
        status=CampaignStatus.SCHEDULED,
        schedule_at=now + timedelta(days=1),
    )

    claimed = send_due_campaigns()
    assert claimed == 1  # only the past-due one

    due.refresh_from_db()
    future.refresh_from_db()
    assert due.status == CampaignStatus.SENT
    assert future.status == CampaignStatus.SCHEDULED  # untouched
    assert WalletMessage.objects.filter(customer_card=customer, body="now").exists()

    # A second tick is a no-op (already SENT, not re-dispatched).
    assert send_due_campaigns() == 0


def test_campaign_list_tenant_scoped(paid_merchant):
    other = factories.MerchantFactory()
    Campaign.objects.create(merchant=paid_merchant, audience="all", message="a")
    Campaign.objects.create(merchant=other, audience="all", message="b")
    client, _ = _client_for(Role.ADMIN, paid_merchant)
    resp = client.get("/api/v1/campaigns")
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 1


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
    # New advanced segments are present; both customers joined just now.
    assert by_key["new"]["count"] == 2
    assert by_key["active"]["count"] == 1  # only `ready` has ledger activity
    assert "birthday_month" in by_key
    # One per-card segment is surfaced for the program above.
    assert by_key[f"card:{card.id}"]["count"] == 1


def test_segment_birthday_month_resolves(paid_merchant):
    from datetime import date

    from django.utils import timezone

    from messaging.segments import resolve

    this_month = timezone.now().month
    match = factories.CustomerCardFactory(
        merchant=paid_merchant, birthday=date(1990, this_month, 15)
    )
    other_month = 1 if this_month != 1 else 2
    factories.CustomerCardFactory(merchant=paid_merchant, birthday=date(1990, other_month, 15))

    ids = set(resolve(paid_merchant, "birthday_month").values_list("id", flat=True))
    assert match.id in ids
    assert len(ids) == 1


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
        {"enabled": True, "template": "hbd!"},
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


def test_starter_can_enable_welcome_but_not_engagement(merchant):
    # Engagement automations are Growth+; `welcome` is free on every plan.
    activate_plan(merchant, PlanTier.STARTER)
    client, _ = _client_for(Role.ADMIN, merchant)

    welcome = client.patch("/api/v1/automations/welcome", {"enabled": True}, format="json")
    assert welcome.status_code == 200
    assert welcome.json()["enabled"] is True

    birthday = client.patch("/api/v1/automations/birthday", {"enabled": True}, format="json")
    assert birthday.status_code == 402


# ── automation triggers ───────────────────────────────────────────────────────
def test_almost_there_fires_one_stamp_before_reward(merchant, no_cooldown):
    """`almost_there` fires when a stamp lands the card exactly one short."""
    from wallets.models import WalletMessage

    Automation.objects.create(
        merchant=merchant,
        key=AutomationKey.ALMOST_THERE,
        enabled=True,
        template="One more!",
    )
    card = factories.CardFactory(merchant=merchant, stamps_required=2)
    customer = factories.CustomerCardFactory(card=card, merchant=merchant)

    client, _ = _client_for(Role.SCANNER, merchant)
    resp = client.post(
        "/api/v1/loyalty/stamp",
        {"customer_card_id": str(customer.id), "delta": 1},
        format="json",
    )
    assert resp.status_code == 200
    assert WalletMessage.objects.filter(customer_card=customer, body="One more!").exists()


def test_push_automation_fires_free_on_stamp(merchant, no_cooldown):
    """An enabled automation reaches the customer via the free wallet channel —
    no capability or quota required (works on a non-paid merchant)."""
    from wallets.models import WalletMessage

    Automation.objects.create(
        merchant=merchant,
        key=AutomationKey.REWARD_READY,
        enabled=True,
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
    assert WalletMessage.objects.filter(
        customer_card=customer, body="Your reward is ready!"
    ).exists()


def test_daily_scan_fires_birthday(paid_merchant):
    from datetime import date

    from messaging.automation import run_daily_scan

    Automation.objects.create(
        merchant=paid_merchant,
        key=AutomationKey.BIRTHDAY,
        enabled=True,
        template="hbd",
    )
    today = date(2026, 6, 29)
    factories.CustomerCardFactory(merchant=paid_merchant, birthday=date(1990, 6, 29))
    factories.CustomerCardFactory(merchant=paid_merchant, birthday=date(1990, 1, 1))

    fired = run_daily_scan(today)
    assert fired == 1
