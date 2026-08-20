"""Tests for the dashboard & analytics endpoints (contract §3.6 · Phase 3).

Covers the HTTP layer: RBAC (Admin+, Owner for staff creation), tenant scoping,
the contract JSON shapes, the customer filters, the analytics aggregations, and
the Google-class sync seam (faked — no Celery/broker required).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from core import ledger
from core.enums import CustomerCardStatus, Role, WalletPlatform
from core.models import Card, Redemption, StaffUser, StampLedger, WalletRegistration
from tests import factories

pytestmark = pytest.mark.django_db


def _client_for(role, merchant):
    """An APIClient authenticated as a fresh staff member with ``role``."""
    from rest_framework_simplejwt.tokens import RefreshToken

    staff = factories.StaffUserFactory(merchant=merchant, role=role)
    client = APIClient()
    access = RefreshToken.for_user(staff.user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client, staff


@pytest.fixture(autouse=True)
def google_sync_calls(monkeypatch):
    """Record sync_google_class.delay(card_id) instead of hitting the broker."""
    from wallets.tasks import sync_google_class

    calls: list = []
    monkeypatch.setattr(sync_google_class, "delay", lambda card_id: calls.append(card_id))
    return calls


# ── Cards ─────────────────────────────────────────────────────────────────────
def test_list_cards_only_own_merchant(auth_client, merchant):
    mine = factories.CardFactory(merchant=merchant, name="Mine")
    factories.CardFactory(name="Theirs")  # other merchant
    resp = auth_client.get("/api/v1/cards")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()["results"]]
    assert names == ["Mine"]
    assert str(mine.id) in [c["id"] for c in resp.json()["results"]]


def test_create_card_sets_merchant_and_syncs_google(auth_client, merchant, google_sync_calls):
    resp = auth_client.post(
        "/api/v1/cards",
        {"name": "Coffee", "stamps_required": 8, "reward_title": "Free latte"},
        format="json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Coffee"
    assert body["stamps_required"] == 8
    assert body["status"] == "DRAFT"  # model default

    card = Card.objects.get(id=body["id"])
    assert card.merchant_id == merchant.id
    # Google class re-provision was enqueued for the new card.
    assert google_sync_calls == [str(card.id)]
    # A primary Reward row is created so the redeem flow works (note 7).
    reward = card.rewards.get()
    assert reward.title == "Free latte"
    assert reward.threshold == 8
    assert reward.is_active is True


def test_patch_card_updates_and_syncs(auth_client, merchant, google_sync_calls):
    card = factories.CardFactory(merchant=merchant, reward_title="Old")
    resp = auth_client.patch(f"/api/v1/cards/{card.id}", {"reward_title": "New"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["reward_title"] == "New"
    card.refresh_from_db()
    assert card.reward_title == "New"
    assert google_sync_calls == [str(card.id)]
    # The primary Reward row tracks the card's reward title (note 7).
    assert card.rewards.get().title == "New"


def test_patch_other_merchant_card_is_404(auth_client):
    other = factories.CardFactory()  # different merchant
    resp = auth_client.patch(f"/api/v1/cards/{other.id}", {"reward_title": "x"}, format="json")
    assert resp.status_code == 404


def test_scanner_cannot_access_cards(merchant):
    client, _ = _client_for(Role.SCANNER, merchant)
    resp = client.get("/api/v1/cards")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "PERMISSION_DENIED"


def test_cards_require_auth(api_client):
    resp = api_client.get("/api/v1/cards")
    assert resp.status_code == 401


# ── Locations ─────────────────────────────────────────────────────────────────
def test_create_and_list_locations(auth_client, merchant):
    created = auth_client.post(
        "/api/v1/locations", {"name": "Downtown", "address": "1 Main St"}, format="json"
    )
    assert created.status_code == 201
    assert created.json()["name"] == "Downtown"

    listed = auth_client.get("/api/v1/locations")
    assert listed.status_code == 200
    assert [loc["name"] for loc in listed.json()["results"]] == ["Downtown"]


# ── Staff ─────────────────────────────────────────────────────────────────────
def test_owner_can_create_staff(merchant):
    client, _ = _client_for(Role.OWNER, merchant)
    resp = client.post(
        "/api/v1/staff",
        {"email": "cashier@example.com", "password": "s3cretpw!", "role": "SCANNER"},
        format="json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "cashier@example.com"
    assert body["role"] == "SCANNER"
    new_staff = StaffUser.objects.get(id=body["id"])
    assert new_staff.merchant_id == merchant.id
    assert new_staff.user.check_password("s3cretpw!")


def test_admin_cannot_create_staff(merchant):
    client, _ = _client_for(Role.ADMIN, merchant)
    resp = client.post(
        "/api/v1/staff",
        {"email": "x@example.com", "password": "s3cretpw!", "role": "SCANNER"},
        format="json",
    )
    assert resp.status_code == 403


def test_create_staff_duplicate_email_400(merchant):
    client, _ = _client_for(Role.OWNER, merchant)
    payload = {"email": "dup@example.com", "password": "s3cretpw!", "role": "ADMIN"}
    first = client.post("/api/v1/staff", payload, format="json")
    assert first.status_code == 201
    second = client.post("/api/v1/staff", payload, format="json")
    assert second.status_code == 400
    assert "email" in second.json()["error"]["fields"]


def test_admin_can_list_staff(auth_client, merchant, staff_user):
    resp = auth_client.get("/api/v1/staff")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()["results"]]
    assert str(staff_user.id) in ids


# ── Customers ─────────────────────────────────────────────────────────────────
def test_list_customers_filter_by_status(auth_client, merchant):
    card = factories.CardFactory(merchant=merchant)
    factories.CustomerCardFactory(card=card, merchant=merchant, status=CustomerCardStatus.ACTIVE)
    blocked = factories.CustomerCardFactory(
        card=card, merchant=merchant, status=CustomerCardStatus.BLOCKED
    )

    resp = auth_client.get("/api/v1/customers?status=BLOCKED")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert [c["id"] for c in results] == [str(blocked.id)]


def test_list_customers_scoped_to_merchant(auth_client, merchant):
    card = factories.CardFactory(merchant=merchant)
    factories.CustomerCardFactory(card=card, merchant=merchant)
    factories.CustomerCardFactory()  # other merchant
    resp = auth_client.get("/api/v1/customers")
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 1


# ── Analytics ─────────────────────────────────────────────────────────────────
def test_analytics_summary(auth_client, merchant, reward, no_cooldown):
    card = reward.card
    card.merchant = merchant
    card.save(update_fields=["merchant"])

    c1 = factories.CustomerCardFactory(card=card, merchant=merchant)
    c2 = factories.CustomerCardFactory(card=card, merchant=merchant)
    factories.CustomerCardFactory(card=card, merchant=merchant)  # c3, no activity

    # c1 is a returning customer (2 stamps); c2 has a single stamp.
    ledger.add_stamp(c1)
    ledger.add_stamp(c1)
    ledger.add_stamp(c2)

    Redemption.objects.create(customer_card=c1, reward=reward, merchant=merchant)
    WalletRegistration.objects.create(
        customer_card=c1, platform=WalletPlatform.APPLE, is_active=True
    )
    WalletRegistration.objects.create(
        customer_card=c2, platform=WalletPlatform.GOOGLE, is_active=True
    )

    resp = auth_client.get("/api/v1/analytics/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enrollments"] == 3
    assert body["active_cards"] == 3
    assert body["redemptions"] == 1
    assert body["apple_count"] == 1
    assert body["google_count"] == 1
    # 1 of 3 customers is returning.
    assert body["repeat_rate"] == pytest.approx(1 / 3, abs=1e-4)


def test_analytics_summary_zero_customers(auth_client):
    resp = auth_client.get("/api/v1/analytics/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enrollments"] == 0
    assert body["repeat_rate"] == 0.0


def test_analytics_excludes_inactive_wallet_registrations(auth_client, merchant):
    card = factories.CardFactory(merchant=merchant)
    cc = factories.CustomerCardFactory(card=card, merchant=merchant)
    WalletRegistration.objects.create(
        customer_card=cc, platform=WalletPlatform.APPLE, is_active=False
    )
    resp = auth_client.get("/api/v1/analytics/summary")
    assert resp.json()["apple_count"] == 0  # inactive registration not counted


def test_analytics_summary_without_a_range_is_all_time(auth_client, merchant, card, reward):
    """The Overview page asks with no range and must keep its lifetime totals."""
    old = factories.CustomerCardFactory(card=card, merchant=merchant)
    ledger.add_stamp(old)
    StampLedger.objects.filter(customer_card=old).update(
        created_at=timezone.now() - timedelta(days=400)
    )

    body = auth_client.get("/api/v1/analytics/summary").json()
    # Counted even though its only activity is 400 days old.
    assert body["enrollments"] == 1
    assert body["active_cards"] == 1


def test_analytics_summary_with_a_range_describes_that_window(auth_client, merchant, card, reward):
    """Every KPI counts what happened inside the window (and matches the charts)."""
    # inside: joined + stamped twice → a returning customer.
    inside = factories.CustomerCardFactory(card=card, merchant=merchant)
    ledger.record_enrollment(inside)
    ledger.add_stamp(inside)
    ledger.add_stamp(inside, force=True)

    # one_stamp: active in the window, but not returning.
    one_stamp = factories.CustomerCardFactory(card=card, merchant=merchant)
    ledger.record_enrollment(one_stamp)
    ledger.add_stamp(one_stamp)

    # outside: all of its activity is backdated well before the window.
    outside = factories.CustomerCardFactory(card=card, merchant=merchant)
    ledger.record_enrollment(outside)
    ledger.add_stamp(outside)
    StampLedger.objects.filter(customer_card=outside).update(
        created_at=timezone.now() - timedelta(days=400)
    )

    today = timezone.localdate()
    body = auth_client.get(
        f"/api/v1/analytics/summary?from={today - timedelta(days=7)}&to={today}"
    ).json()

    # `outside` is excluded everywhere: 2 joins, 2 cards active, 1 of them returning.
    assert body["enrollments"] == 2
    assert body["active_cards"] == 2
    assert body["repeat_rate"] == pytest.approx(0.5)

    # The enrollments tile agrees with the joins chart over the same range.
    points = auth_client.get(
        f"/api/v1/analytics/timeseries?metric=joins&from={today - timedelta(days=7)}&to={today}"
    ).json()["points"]
    assert sum(p["value"] for p in points) == body["enrollments"]


def test_analytics_summary_range_counts_redemptions_in_the_window(
    auth_client, merchant, card, reward
):
    cc = factories.CustomerCardFactory(card=card, merchant=merchant, stamp_count=10)
    ledger.redeem_reward(cc, reward=reward)

    today = timezone.localdate()
    scoped = f"?from={today - timedelta(days=7)}&to={today}"
    assert auth_client.get(f"/api/v1/analytics/summary{scoped}").json()["redemptions"] == 1

    # Backdate it out of the window and the tile drops it.
    StampLedger.objects.filter(customer_card=cc).update(
        created_at=timezone.now() - timedelta(days=400)
    )
    assert auth_client.get(f"/api/v1/analytics/summary{scoped}").json()["redemptions"] == 0


def test_analytics_summary_rejects_a_bad_date(auth_client):
    assert auth_client.get("/api/v1/analytics/summary?from=nope").status_code == 400


def test_analytics_wallet_split_honours_the_date_range(auth_client, merchant):
    """Unlike /summary, the split counts only passes added inside the window."""
    card = factories.CardFactory(merchant=merchant)
    inside = factories.CustomerCardFactory(card=card, merchant=merchant)
    outside = factories.CustomerCardFactory(card=card, merchant=merchant)

    recent = WalletRegistration.objects.create(
        customer_card=inside, platform=WalletPlatform.APPLE, is_active=True
    )
    stale = WalletRegistration.objects.create(
        customer_card=outside, platform=WalletPlatform.GOOGLE, is_active=True
    )
    # created_at is auto_now_add, so backdate the second one past the window.
    WalletRegistration.objects.filter(pk=stale.pk).update(
        created_at=timezone.now() - timedelta(days=400)
    )

    today = timezone.localdate()
    resp = auth_client.get(
        f"/api/v1/analytics/wallet_split?from={today - timedelta(days=7)}&to={today}"
    )
    assert resp.status_code == 200
    assert resp.json() == {"apple_count": 1, "google_count": 0}

    # Widen the range and the backdated Google pass comes back into view.
    resp = auth_client.get(
        f"/api/v1/analytics/wallet_split?from={today - timedelta(days=500)}&to={today}"
    )
    assert resp.json() == {"apple_count": 1, "google_count": 1}
    assert recent.is_active


def test_analytics_wallet_split_rejects_a_bad_date(auth_client):
    assert auth_client.get("/api/v1/analytics/wallet_split?from=nope").status_code == 400


# ── extra coverage: untested branches ─────────────────────────────────────────
def test_get_card_detail(auth_client, merchant):
    card = factories.CardFactory(merchant=merchant, name="Detail")
    resp = auth_client.get(f"/api/v1/cards/{card.id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Detail"


def test_create_staff_rejects_other_merchant_location(merchant):
    client, _ = _client_for(Role.OWNER, merchant)
    foreign_location = factories.LocationFactory()  # belongs to another merchant
    resp = client.post(
        "/api/v1/staff",
        {
            "email": "new@example.com",
            "password": "s3cretpw!",
            "role": "SCANNER",
            "location": str(foreign_location.id),
        },
        format="json",
    )
    assert resp.status_code == 400
    assert "location" in resp.json()["error"]["fields"]
    # The auth User must not be created when staff creation fails.
    from django.contrib.auth import get_user_model

    assert not get_user_model().objects.filter(username="new@example.com").exists()


def test_customers_filter_by_phone_and_card(auth_client, merchant):
    card_a = factories.CardFactory(merchant=merchant)
    card_b = factories.CardFactory(merchant=merchant)
    target = factories.CustomerCardFactory(
        card=card_a, merchant=merchant, customer_phone="+201111111111"
    )
    factories.CustomerCardFactory(card=card_b, merchant=merchant, customer_phone="+209999999999")

    by_phone = auth_client.get("/api/v1/customers?phone=1111111111")
    assert [c["id"] for c in by_phone.json()["results"]] == [str(target.id)]

    by_card = auth_client.get(f"/api/v1/customers?card={card_a.id}")
    assert [c["id"] for c in by_card.json()["results"]] == [str(target.id)]
