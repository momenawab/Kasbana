"""Test-card (demo) tool tests.

Covers the create → pass → delete flow, the role gate, and — the point of the
feature — that demo merchants never leak into the real console surfaces
(directory, analytics, lifecycle).
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminUser
from core.models import Card, CustomerCard, Merchant
from tests import factories

pytestmark = pytest.mark.django_db

URL = "/api/admin/v1/demo-cards"
MERCHANTS = "/api/admin/v1/merchants"

PAYLOAD = {
    "merchant_name": "Cafe Blooms",
    "name": "Coffee Club",
    "stamps_required": 8,
    "reward_title": "Free latte",
    "color_bg": "#0E1B2A",
    "color_fg": "#FFFFFF",
}


def _client(role):
    admin = AdminUser(email=f"{role.lower()}@stampn.net", role=role)
    admin.set_password("supersecret1")
    admin.save()
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return c


@pytest.fixture
def admin_client():
    return _client(AdminRole.SUPER_ADMIN)


def test_create_builds_merchant_card_and_holder(admin_client):
    resp = admin_client.post(URL, PAYLOAD, format="json")
    assert resp.status_code == 201
    body = resp.json()
    assert body["merchant_name"] == "Cafe Blooms"
    assert body["card_name"] == "Coffee Club"

    merchant = Merchant.objects.get(pk=body["merchant_id"])
    assert merchant.is_demo is True
    # The pass reads the brand off the merchant, so the typed name must land there.
    assert merchant.name == "Cafe Blooms"

    card = Card.objects.get(pk=body["card_id"])
    assert card.status == "ACTIVE"  # a draft has no live pass to show
    # A pass exists only for an enrolled holder.
    assert CustomerCard.objects.filter(card=card).count() == 1


def test_demo_merchant_hidden_from_directory(admin_client):
    factories.MerchantFactory(name="Real Shop")
    admin_client.post(URL, PAYLOAD, format="json")

    names = [r["name"] for r in admin_client.get(MERCHANTS).json()["results"]]
    assert "Real Shop" in names
    assert "Cafe Blooms" not in names  # demo never pollutes the directory


def test_demo_merchant_excluded_from_platform_analytics(admin_client):
    from django.core.cache import cache

    from console import analytics_platform

    factories.MerchantFactory()
    before = analytics_platform.platform_analytics()["merchants"]["total"]

    admin_client.post(URL, PAYLOAD, format="json")
    cache.delete(analytics_platform._CACHE_KEY)  # the snapshot is cached; bust it

    after = analytics_platform.platform_analytics()["merchants"]["total"]
    assert after == before  # a sales demo must not read as a signup


def test_list_returns_created_cards(admin_client):
    admin_client.post(URL, PAYLOAD, format="json")
    rows = admin_client.get(URL).json()
    assert len(rows) == 1
    assert rows[0]["merchant_name"] == "Cafe Blooms"


def test_delete_removes_card_and_demo_merchant(admin_client):
    created = admin_client.post(URL, PAYLOAD, format="json").json()

    assert admin_client.delete(f"{URL}/{created['card_id']}").status_code == 204
    assert not Card.objects.filter(pk=created["card_id"]).exists()
    assert not Merchant.objects.filter(pk=created["merchant_id"]).exists()


def test_pass_endpoint_returns_wallet_urls(admin_client):
    created = admin_client.post(URL, PAYLOAD, format="json").json()
    resp = admin_client.get(f"{URL}/{created['card_id']}/pass")
    assert resp.status_code == 200
    # Keys are always present; values are null without wallet credentials (CI).
    assert "apple_pass_url" in resp.json()
    assert "google_save_url" in resp.json()


def test_pass_endpoint_rejects_a_real_merchants_card(admin_client, merchant):
    """The tool must never hand out a real customer's pass."""
    card = factories.CardFactory(merchant=merchant)
    assert admin_client.get(f"{URL}/{card.id}/pass").status_code == 404


# ── live stamping (the pitch demo) ────────────────────────────────────────────
def test_stamp_adds_to_the_balance(admin_client):
    created = admin_client.post(URL, PAYLOAD, format="json").json()
    assert created["stamp_count"] == 0

    resp = admin_client.post(f"{URL}/{created['card_id']}/stamp", {"delta": 1}, format="json")
    assert resp.status_code == 200
    assert resp.json()["stamp_count"] == 1
    assert resp.json()["stamps_required"] == 8


def test_stamp_accepts_a_delta(admin_client):
    created = admin_client.post(URL, PAYLOAD, format="json").json()
    body = admin_client.post(
        f"{URL}/{created['card_id']}/stamp", {"delta": 5}, format="json"
    ).json()
    assert body["stamp_count"] == 5
    assert body["reward_ready"] is False


def test_stamping_to_the_threshold_flags_reward_ready(admin_client):
    created = admin_client.post(URL, PAYLOAD, format="json").json()
    body = admin_client.post(
        f"{URL}/{created['card_id']}/stamp", {"delta": 8}, format="json"
    ).json()
    assert body["stamp_count"] == 8
    assert body["reward_ready"] is True


def test_repeated_stamps_are_not_blocked_by_anti_fraud(admin_client):
    """The pitch must not stall on the 30s cooldown or the 12/day cap.

    Both guards protect real reward economics; a demo card has none. Back-to-back
    stamps here would raise CooldownActive on a real card.
    """
    created = admin_client.post(URL, PAYLOAD, format="json").json()
    card_id = created["card_id"]

    for _ in range(15):  # past MAX_STAMPS_PER_CARD_PER_DAY (12)
        resp = admin_client.post(f"{URL}/{card_id}/stamp", {"delta": 1}, format="json")
        assert resp.status_code == 200
    assert resp.json()["stamp_count"] == 15


def test_reset_zeroes_the_card_to_pitch_again(admin_client):
    created = admin_client.post(URL, PAYLOAD, format="json").json()
    admin_client.post(f"{URL}/{created['card_id']}/stamp", {"delta": 4}, format="json")

    body = admin_client.post(f"{URL}/{created['card_id']}/reset", format="json").json()
    assert body["stamp_count"] == 0
    assert body["reward_ready"] is False


def test_stamp_rejects_a_real_merchants_card(admin_client, merchant):
    """The console's demo stamper must never touch a real customer's balance."""
    card = factories.CardFactory(merchant=merchant)
    resp = admin_client.post(f"{URL}/{card.id}/stamp", {"delta": 1}, format="json")
    assert resp.status_code == 404


def test_read_only_cannot_stamp(admin_client):
    created = admin_client.post(URL, PAYLOAD, format="json").json()
    ro = _client(AdminRole.READ_ONLY)
    assert (
        ro.post(f"{URL}/{created['card_id']}/stamp", {"delta": 1}, format="json").status_code == 403
    )


# ── access ────────────────────────────────────────────────────────────────────
def test_sales_can_create(admin_client):
    sales = _client(AdminRole.SALES)
    assert sales.post(URL, PAYLOAD, format="json").status_code == 201


def test_read_only_cannot_create():
    ro = _client(AdminRole.READ_ONLY)
    assert ro.post(URL, PAYLOAD, format="json").status_code == 403
    assert ro.get(URL).status_code == 403
