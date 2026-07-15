"""Tests for dashboard Phase 1.6 completeness endpoints (contract §3.6).

Covers card stats/QR, uploads, customer detail/delete/timeline + filters,
analytics (timeseries/retention/by_location/activity), location patch/stats,
and staff patch/invite.
"""

from __future__ import annotations

import io
from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import StaffInvite
from core import ledger
from core.enums import Role, WalletPlatform
from core.models import CustomerCard, Redemption, WalletRegistration
from tests import factories

pytestmark = pytest.mark.django_db


def _client_for(role, merchant):
    from rest_framework_simplejwt.tokens import RefreshToken

    staff = factories.StaffUserFactory(merchant=merchant, role=role)
    client = APIClient()
    access = RefreshToken.for_user(staff.user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client, staff


# ── Cards: aggregates, stats, QR ─────────────────────────────────────────────
def test_card_list_includes_aggregates(auth_client, merchant, reward, no_cooldown):
    card = reward.card
    card.merchant = merchant
    card.save(update_fields=["merchant"])

    c1 = factories.CustomerCardFactory(card=card, merchant=merchant)
    c2 = factories.CustomerCardFactory(card=card, merchant=merchant)
    ledger.add_stamp(c1)
    ledger.add_stamp(c1)
    ledger.add_stamp(c2)
    Redemption.objects.create(customer_card=c1, reward=reward, merchant=merchant)

    resp = auth_client.get("/api/v1/cards")
    assert resp.status_code == 200
    item = next(c for c in resp.json()["results"] if c["id"] == str(card.id))
    assert item["holders"] == 2
    assert item["stamps_issued"] == 3
    assert item["rewards_redeemed"] == 1


def test_card_stats(auth_client, merchant, reward, no_cooldown):
    card = reward.card
    card.merchant = merchant
    card.save(update_fields=["merchant"])

    c1 = factories.CustomerCardFactory(card=card, merchant=merchant)
    c2 = factories.CustomerCardFactory(card=card, merchant=merchant)
    ledger.add_stamp(c1)
    ledger.add_stamp(c1)
    ledger.add_stamp(c2)
    Redemption.objects.create(customer_card=c1, reward=reward, merchant=merchant)
    WalletRegistration.objects.create(
        customer_card=c1, platform=WalletPlatform.APPLE, is_active=True
    )

    resp = auth_client.get(f"/api/v1/cards/{card.id}/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["holders"] == 2
    assert body["stamps_issued"] == 3
    assert body["rewards_redeemed"] == 1
    assert body["completion_rate"] == 0.5
    assert body["apple_count"] == 1
    assert body["google_count"] == 0


def test_card_qr_returns_join_url_and_svg(auth_client, merchant):
    card = factories.CardFactory(merchant=merchant)
    resp = auth_client.get(f"/api/v1/cards/{card.id}/qr")
    assert resp.status_code == 200
    body = resp.json()
    assert body["join_url"].startswith("http")
    assert "<svg" in body["qr_svg"]
    assert "poster_pdf_url" in body


def test_card_qr_token_is_stable_across_calls(auth_client, merchant):
    """The join URL must not change between views (printed posters keep working)."""
    from core.models import EnrollmentToken

    card = factories.CardFactory(merchant=merchant)
    first = auth_client.get(f"/api/v1/cards/{card.id}/qr").json()["join_url"]
    second = auth_client.get(f"/api/v1/cards/{card.id}/qr").json()["join_url"]
    assert first == second
    # And it didn't leak a token row per request.
    assert EnrollmentToken.objects.filter(card=card, is_active=True).count() == 1


# ── Uploads ───────────────────────────────────────────────────────────────────
def test_upload_image_returns_url(auth_client, merchant, settings, tmpdir):
    settings.MEDIA_ROOT = str(tmpdir)
    image = io.BytesIO(b"fake-image-data")
    image.name = "logo.png"
    resp = auth_client.post("/api/v1/uploads", {"file": image}, format="multipart")
    assert resp.status_code == 201
    assert resp.json()["url"].startswith("http")


def test_upload_rejects_oversized(auth_client, settings):
    settings.UPLOAD_MAX_SIZE_BYTES = 10
    image = io.BytesIO(b"fake-image-data-that-is-too-big")
    image.name = "logo.png"
    resp = auth_client.post("/api/v1/uploads", {"file": image}, format="multipart")
    assert resp.status_code == 413


# ── Customers: detail / delete / timeline / filters ───────────────────────────
def test_customer_detail_includes_birthday(auth_client, merchant):
    card = factories.CardFactory(merchant=merchant)
    birthday = date(1990, 5, 20)
    customer = factories.CustomerCardFactory(
        card=card, merchant=merchant, customer_name="Ali", birthday=birthday
    )
    resp = auth_client.get(f"/api/v1/customers/{customer.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(customer.id)
    assert body["customer_name"] == "Ali"
    assert body["birthday"] == "1990-05-20"


def test_customer_delete_pdpl(auth_client, merchant):
    card = factories.CardFactory(merchant=merchant)
    customer = factories.CustomerCardFactory(card=card, merchant=merchant)
    resp = auth_client.delete(f"/api/v1/customers/{customer.id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert not CustomerCard.objects.filter(pk=customer.id).exists()


def test_customer_timeline(auth_client, merchant, reward, no_cooldown):
    card = reward.card
    card.merchant = merchant
    card.save(update_fields=["merchant"])
    customer = factories.CustomerCardFactory(card=card, merchant=merchant)
    for _ in range(reward.threshold):
        ledger.add_stamp(customer)
    ledger.redeem_reward(customer, reward)

    resp = auth_client.get(f"/api/v1/customers/{customer.id}/timeline")
    assert resp.status_code == 200
    events = resp.json()["results"]
    types = [e["event_type"] for e in events]
    assert "stamp" in types
    assert "redeem" in types


def test_customer_timeline_does_not_duplicate_redemptions(
    auth_client, merchant, reward, no_cooldown
):
    card = reward.card
    card.merchant = merchant
    card.save(update_fields=["merchant"])
    customer = factories.CustomerCardFactory(card=card, merchant=merchant)
    for _ in range(reward.threshold):
        ledger.add_stamp(customer)
    ledger.redeem_reward(customer, reward)

    resp = auth_client.get(f"/api/v1/customers/{customer.id}/timeline")
    assert resp.status_code == 200
    events = resp.json()["results"]
    assert [e["event_type"] for e in events].count("redeem") == 1


def test_customer_list_wallet_platform_has_no_n_plus_1(
    auth_client, merchant, django_assert_max_num_queries
):
    """The active-registration prefetch must keep the query count flat as rows grow."""
    card = factories.CardFactory(merchant=merchant)
    for _ in range(5):
        cc = factories.CustomerCardFactory(card=card, merchant=merchant)
        WalletRegistration.objects.create(
            customer_card=cc, platform=WalletPlatform.APPLE, is_active=True
        )

    # A handful of queries (auth/staff + customers + prefetch + count) — never
    # one-per-customer. Generous ceiling that still catches a real N+1.
    with django_assert_max_num_queries(12):
        resp = auth_client.get("/api/v1/customers")
    assert resp.status_code == 200
    platforms = [c["wallet_platform"] for c in resp.json()["results"]]
    assert platforms and all(p == "APPLE" for p in platforms)


def test_customer_list_segment_reward_ready(auth_client, merchant, reward, no_cooldown):
    card = reward.card
    card.merchant = merchant
    card.save(update_fields=["merchant"])
    ready = factories.CustomerCardFactory(card=card, merchant=merchant, stamp_count=5)
    not_ready = factories.CustomerCardFactory(card=card, merchant=merchant, stamp_count=1)

    resp = auth_client.get("/api/v1/customers?segment=reward_ready")
    assert resp.status_code == 200
    ids = {c["id"] for c in resp.json()["results"]}
    assert str(ready.id) in ids
    assert str(not_ready.id) not in ids


def test_customer_list_segment_lapsed(auth_client, merchant):
    card = factories.CardFactory(merchant=merchant)
    old = factories.CustomerCardFactory(
        card=card, merchant=merchant, last_event_at=timezone.now() - timedelta(days=40)
    )
    recent = factories.CustomerCardFactory(
        card=card, merchant=merchant, last_event_at=timezone.now() - timedelta(days=5)
    )

    resp = auth_client.get("/api/v1/customers?segment=lapsed")
    assert resp.status_code == 200
    ids = {c["id"] for c in resp.json()["results"]}
    assert str(old.id) in ids
    assert str(recent.id) not in ids


def test_customer_list_search(auth_client, merchant):
    card = factories.CardFactory(merchant=merchant)
    target = factories.CustomerCardFactory(
        card=card, merchant=merchant, customer_name="Searchable Name"
    )
    factories.CustomerCardFactory(card=card, merchant=merchant, customer_name="Other")

    resp = auth_client.get("/api/v1/customers?search=Searchable")
    assert resp.status_code == 200
    assert [c["id"] for c in resp.json()["results"]] == [str(target.id)]


# ── Analytics ─────────────────────────────────────────────────────────────────
def test_analytics_timeseries_stamps(auth_client, merchant, reward, no_cooldown):
    card = reward.card
    card.merchant = merchant
    card.save(update_fields=["merchant"])
    customer = factories.CustomerCardFactory(card=card, merchant=merchant)
    ledger.add_stamp(customer)
    ledger.add_stamp(customer)

    today = timezone.localdate().isoformat()
    resp = auth_client.get(f"/api/v1/analytics/timeseries?metric=stamps&from={today}&to={today}")
    assert resp.status_code == 200
    point = next(p for p in resp.json()["points"] if p["date"] == today)
    assert point["value"] == 2


def test_analytics_retention_shape(auth_client, merchant):
    today = timezone.localdate().isoformat()
    resp = auth_client.get(f"/api/v1/analytics/retention?from={today}&to={today}")
    assert resp.status_code == 200
    body = resp.json()
    assert "curve" in body
    assert "at_risk_count" in body
    assert len(body["curve"]) == 8


def test_analytics_retention_values(auth_client, merchant, reward, no_cooldown):
    card = reward.card
    card.merchant = merchant
    card.save(update_fields=["merchant"])
    customer = factories.CustomerCardFactory(card=card, merchant=merchant)

    # Enroll + stamp on day 0 -> retained on day 0.
    today = timezone.localdate()
    ledger.add_stamp(customer)
    # Stamp again tomorrow -> retained on day 1.
    second = ledger.add_stamp(customer)
    second.created_at = timezone.now() + timedelta(days=1)
    second.save(update_fields=["created_at"])

    resp = auth_client.get(f"/api/v1/analytics/retention?from={today}&to={today}")
    assert resp.status_code == 200
    curve = {p["day"]: p["retained_pct"] for p in resp.json()["curve"]}
    assert curve[0] == 1.0
    assert curve[1] == 1.0
    assert curve[2] == 0.0


def test_analytics_by_location(auth_client, merchant, reward, no_cooldown):
    card = reward.card
    card.merchant = merchant
    card.save(update_fields=["merchant"])
    location = factories.LocationFactory(merchant=merchant)
    customer = factories.CustomerCardFactory(card=card, merchant=merchant)
    ledger.add_stamp(customer, location=location)

    today = timezone.localdate().isoformat()
    resp = auth_client.get(f"/api/v1/analytics/by_location?from={today}&to={today}")
    assert resp.status_code == 200
    item = next(r for r in resp.json()["results"] if r["location_id"] == str(location.id))
    assert item["stamps"] == 1


def test_activity_feed(auth_client, merchant, reward, no_cooldown):
    card = reward.card
    card.merchant = merchant
    card.save(update_fields=["merchant"])
    customer = factories.CustomerCardFactory(card=card, merchant=merchant)
    ledger.add_stamp(customer)

    resp = auth_client.get("/api/v1/activity?limit=10")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) >= 1
    assert results[0]["type"] == "stamp"


# ── Locations: patch + stats ──────────────────────────────────────────────────
def test_patch_location(auth_client, merchant):
    location = factories.LocationFactory(merchant=merchant, name="Old")
    resp = auth_client.patch(
        f"/api/v1/locations/{location.id}", {"name": "New", "address": "Updated"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"
    location.refresh_from_db()
    assert location.name == "New"


def test_location_stats(auth_client, merchant, reward, no_cooldown):
    card = reward.card
    card.merchant = merchant
    card.save(update_fields=["merchant"])
    location = factories.LocationFactory(merchant=merchant)
    customer = factories.CustomerCardFactory(card=card, merchant=merchant)
    ledger.add_stamp(customer, location=location)
    Redemption.objects.create(
        customer_card=customer, reward=reward, merchant=merchant, location=location
    )

    resp = auth_client.get(f"/api/v1/locations/{location.id}/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["stamps"] == 1
    assert body["redemptions"] == 1
    assert body["customers"] == 1


# ── Staff: invite + patch + last-owner guard ──────────────────────────────────
def test_staff_invite_creates_pending_invite(merchant):
    owner_client, _ = _client_for(Role.OWNER, merchant)
    location = factories.LocationFactory(merchant=merchant)
    resp = owner_client.post(
        "/api/v1/staff/invite",
        {"email": "invited@example.com", "role": "SCANNER", "location_id": str(location.id)},
        format="json",
    )
    assert resp.status_code == 201
    invite = StaffInvite.objects.get(email="invited@example.com")
    assert invite.merchant_id == merchant.id
    assert invite.role == Role.SCANNER


def test_staff_invite_rejects_other_merchant_location(merchant):
    owner_client, _ = _client_for(Role.OWNER, merchant)
    foreign = factories.LocationFactory()
    resp = owner_client.post(
        "/api/v1/staff/invite",
        {"email": "invited@example.com", "role": "SCANNER", "location_id": str(foreign.id)},
        format="json",
    )
    assert resp.status_code == 400


def test_patch_staff_role_and_location(auth_client, merchant):
    staff = factories.StaffUserFactory(merchant=merchant, role=Role.SCANNER)
    location = factories.LocationFactory(merchant=merchant)
    owner, _ = _client_for(Role.OWNER, merchant)
    resp = owner.patch(
        f"/api/v1/staff/{staff.id}",
        {"role": "ADMIN", "location_id": str(location.id)},
        format="json",
    )
    assert resp.status_code == 200
    staff.refresh_from_db()
    assert staff.role == Role.ADMIN
    assert staff.location_id == location.id


def test_patch_staff_last_owner_blocked(merchant):
    client, owner_staff = _client_for(Role.OWNER, merchant)
    resp = client.patch(f"/api/v1/staff/{owner_staff.id}", {"role": "ADMIN"}, format="json")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


def test_staff_invite_gated_by_max_staff(merchant):
    from billing.services import lock

    client, _ = _client_for(Role.OWNER, merchant)
    lock(merchant)  # locked merchants may not invite staff
    resp = client.post(
        "/api/v1/staff/invite",
        {"email": "invited@example.com", "role": "SCANNER"},
        format="json",
    )
    assert resp.status_code == 402
    assert resp.json()["error"]["code"] == "PLAN_LIMIT"


def test_staff_detail_requires_owner(merchant):
    staff = factories.StaffUserFactory(merchant=merchant)
    admin_client, _ = _client_for(Role.ADMIN, merchant)
    resp = admin_client.patch(f"/api/v1/staff/{staff.id}", {"role": "SCANNER"}, format="json")
    assert resp.status_code == 403


# ── Analytics tier gating: full analytics is Growth+, summary stays basic ────
def test_analytics_full_view_denied_on_starter_returns_402(auth_client, merchant):
    from billing.services import activate_plan
    from core.enums import PlanTier

    activate_plan(merchant, PlanTier.STARTER)  # analytics = "basic"
    resp = auth_client.get("/api/v1/analytics/timeseries?metric=stamps")
    assert resp.status_code == 402
    assert resp.json()["error"]["code"] == "PLAN_LIMIT"


def test_analytics_summary_allowed_on_starter(auth_client, merchant):
    from billing.services import activate_plan
    from core.enums import PlanTier

    activate_plan(merchant, PlanTier.STARTER)  # basic analytics = summary only
    resp = auth_client.get("/api/v1/analytics/summary")
    assert resp.status_code == 200
