"""Tests for the loyalty endpoints (contract §3.6 · Phase 2).

The ledger's balance math + anti-fraud are unit-tested in ``test_ledger.py``;
here we cover the HTTP layer: auth/role, tenant scoping, the contract JSON
shapes, the error envelope, and the wallet ``push_update`` seam (faked, per the
contract's interface-test guidance — no Redis/Celery required).
"""

from __future__ import annotations

import pytest

from core.models import StampLedger
from tests import factories

pytestmark = pytest.mark.django_db

STAMP_URL = "/api/v1/loyalty/stamp"
REDEEM_URL = "/api/v1/loyalty/redeem"


@pytest.fixture(autouse=True)
def push_calls(monkeypatch):
    """Replace the wallet façade's ``push_update`` with a recorder.

    Autouse so no test ever reaches the real Celery enqueue (which would need a
    broker). Tests that care assert against the recorded cards.
    """
    calls: list = []
    monkeypatch.setattr("wallets.service.push_update", lambda card: calls.append(card))
    return calls


# ── stamp ─────────────────────────────────────────────────────────────────────
def test_stamp_adds_one_and_pushes(auth_client, customer_card, push_calls):
    resp = auth_client.post(STAMP_URL, {"customer_card_id": str(customer_card.id)}, format="json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_card_id"] == str(customer_card.id)
    assert body["stamp_count"] == 1
    assert body["stamps_required"] == customer_card.card.stamps_required
    assert body["reward_ready"] is False

    customer_card.refresh_from_db()
    assert customer_card.stamp_count == 1
    assert StampLedger.objects.filter(customer_card=customer_card, event_type="STAMP").count() == 1
    # The wallet pass update was requested exactly once.
    assert len(push_calls) == 1
    assert push_calls[0].id == customer_card.id


def test_stamp_binds_staff_and_location(auth_client, customer_card, merchant, staff_user):
    location = factories.LocationFactory(merchant=merchant)
    staff_user.location = location
    staff_user.save(update_fields=["location"])

    resp = auth_client.post(STAMP_URL, {"customer_card_id": str(customer_card.id)}, format="json")
    assert resp.status_code == 200

    entry = StampLedger.objects.get(customer_card=customer_card, event_type="STAMP")
    assert entry.staff_id == staff_user.id
    assert entry.location_id == location.id


def test_stamp_reward_ready_when_threshold_reached(auth_client, customer_card):
    customer_card.stamp_count = customer_card.card.stamps_required - 1
    customer_card.save(update_fields=["stamp_count"])

    resp = auth_client.post(STAMP_URL, {"customer_card_id": str(customer_card.id)}, format="json")
    assert resp.status_code == 200
    assert resp.json()["reward_ready"] is True


def test_stamp_cooldown_returns_429(auth_client, customer_card):
    first = auth_client.post(STAMP_URL, {"customer_card_id": str(customer_card.id)}, format="json")
    assert first.status_code == 200
    # Immediate second stamp trips the per-card cooldown.
    second = auth_client.post(STAMP_URL, {"customer_card_id": str(customer_card.id)}, format="json")
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "COOLDOWN_ACTIVE"


def test_stamp_rejects_zero_delta(auth_client, customer_card):
    resp = auth_client.post(
        STAMP_URL, {"customer_card_id": str(customer_card.id), "delta": 0}, format="json"
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "delta" in resp.json()["error"]["fields"]


def test_stamp_requires_auth(api_client, customer_card):
    resp = api_client.post(STAMP_URL, {"customer_card_id": str(customer_card.id)}, format="json")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_stamp_other_merchant_card_is_404(auth_client, push_calls):
    other = factories.CustomerCardFactory()  # different merchant
    resp = auth_client.post(STAMP_URL, {"customer_card_id": str(other.id)}, format="json")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"
    assert push_calls == []  # nothing mutated, nothing pushed


# ── redeem ────────────────────────────────────────────────────────────────────
def test_redeem_success_decrements_balance(auth_client, customer_card, reward, push_calls):
    customer_card.stamp_count = reward.threshold
    customer_card.save(update_fields=["stamp_count"])

    resp = auth_client.post(
        REDEEM_URL,
        {"customer_card_id": str(customer_card.id), "reward_id": str(reward.id)},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "CLAIMED"
    assert body["stamp_count"] == 0
    assert "redemption_id" in body

    customer_card.refresh_from_db()
    assert customer_card.stamp_count == 0
    assert StampLedger.objects.filter(customer_card=customer_card, event_type="REDEEM").count() == 1
    assert len(push_calls) == 1


def test_redeem_not_ready_returns_422(auth_client, customer_card, reward):
    # Balance below threshold.
    assert customer_card.stamp_count < reward.threshold
    resp = auth_client.post(
        REDEEM_URL,
        {"customer_card_id": str(customer_card.id), "reward_id": str(reward.id)},
        format="json",
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "REWARD_NOT_READY"


def test_redeem_reward_from_other_program_is_404(auth_client, customer_card, merchant):
    customer_card.stamp_count = 99
    customer_card.save(update_fields=["stamp_count"])
    # A reward attached to a *different* card (program) of the same merchant.
    other_card = factories.CardFactory(merchant=merchant)
    foreign_reward = factories.RewardFactory(card=other_card, threshold=1)

    resp = auth_client.post(
        REDEEM_URL,
        {"customer_card_id": str(customer_card.id), "reward_id": str(foreign_reward.id)},
        format="json",
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# ── card state ────────────────────────────────────────────────────────────────
def test_get_card_state(auth_client, customer_card):
    customer_card.stamp_count = 3
    customer_card.save(update_fields=["stamp_count"])

    resp = auth_client.get(f"/api/v1/loyalty/cards/{customer_card.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_card_id"] == str(customer_card.id)
    assert body["stamp_count"] == 3
    assert body["stamps_required"] == customer_card.card.stamps_required
    assert body["status"] == "ACTIVE"
    assert body["reward_ready"] is False


def test_get_card_state_other_merchant_is_404(auth_client):
    other = factories.CustomerCardFactory()
    resp = auth_client.get(f"/api/v1/loyalty/cards/{other.id}")
    assert resp.status_code == 404


# ── idempotency ───────────────────────────────────────────────────────────────
def test_stamp_with_idempotency_key_replays_first_result(auth_client, customer_card, push_calls):
    """A retried stamp (same Idempotency-Key) returns the first result and does
    NOT add a second stamp — even though a keyless retry would (or would 429)."""
    headers = {"HTTP_IDEMPOTENCY_KEY": "tap-1"}
    first = auth_client.post(
        STAMP_URL, {"customer_card_id": str(customer_card.id)}, format="json", **headers
    )
    second = auth_client.post(
        STAMP_URL, {"customer_card_id": str(customer_card.id)}, format="json", **headers
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert second.json()["stamp_count"] == 1  # not 2

    customer_card.refresh_from_db()
    assert customer_card.stamp_count == 1
    assert StampLedger.objects.filter(customer_card=customer_card, event_type="STAMP").count() == 1
    assert len(push_calls) == 1  # the mutation (and its pass push) ran once


def test_stamp_distinct_keys_are_independent(auth_client, customer_card, no_cooldown):
    """Different keys are different actions — the second still stamps."""
    r1 = auth_client.post(
        STAMP_URL,
        {"customer_card_id": str(customer_card.id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY="tap-1",
    )
    r2 = auth_client.post(
        STAMP_URL,
        {"customer_card_id": str(customer_card.id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY="tap-2",
    )
    assert r1.json()["stamp_count"] == 1
    assert r2.json()["stamp_count"] == 2


def test_stamp_failed_mutation_releases_key(auth_client, customer_card):
    """If the mutation fails (cooldown), the key is released so a real retry can
    still succeed once the condition clears — it isn't locked to the error."""
    auth_client.post(
        STAMP_URL,
        {"customer_card_id": str(customer_card.id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY="k1",
    )
    # Second stamp, different key, trips the cooldown (429) — its key must not
    # persist a stored response.
    blocked = auth_client.post(
        STAMP_URL,
        {"customer_card_id": str(customer_card.id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY="k2",
    )
    assert blocked.status_code == 429
    from loyalty.models import IdempotencyRecord

    assert not IdempotencyRecord.objects.filter(key="k2").exists()


# ── scan (cashier QR resolve) ─────────────────────────────────────────────────
SCAN_URL = "/api/v1/loyalty/scan"


def _barcode(customer_card) -> str:
    """The payload encoded in the wallet pass QR (Apple + Google builders)."""
    from core import constants

    return f"{constants.PASS_BARCODE_PREFIX}{customer_card.id.hex}"


def test_scan_resolves_card_state(auth_client, customer_card, reward):
    customer_card.stamp_count = 4
    customer_card.save(update_fields=["stamp_count"])

    resp = auth_client.post(SCAN_URL, {"code": _barcode(customer_card)}, format="json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_card_id"] == str(customer_card.id)
    assert body["stamp_count"] == 4
    assert body["stamps_required"] == customer_card.card.stamps_required
    assert body["reward_ready"] is False
    assert body["status"] == "ACTIVE"
    # The program's active reward is surfaced for one-tap redeem.
    assert body["reward_id"] == str(reward.id)
    assert body["reward_title"] == reward.title


def test_scan_is_read_only(auth_client, customer_card, push_calls):
    before = customer_card.stamp_count
    auth_client.post(SCAN_URL, {"code": _barcode(customer_card)}, format="json")
    customer_card.refresh_from_db()
    assert customer_card.stamp_count == before  # scan never mutates the ledger
    assert push_calls == []  # nor pushes a pass update


def test_scan_malformed_code_is_422(auth_client):
    resp = auth_client.post(SCAN_URL, {"code": "not-a-wallet-code"}, format="json")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "code" in resp.json()["error"]["fields"]


def test_scan_other_merchant_card_is_404(auth_client):
    other = factories.CustomerCardFactory()  # different merchant
    resp = auth_client.post(SCAN_URL, {"code": _barcode(other)}, format="json")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_scan_requires_auth(api_client, customer_card):
    resp = api_client.post(SCAN_URL, {"code": _barcode(customer_card)}, format="json")
    assert resp.status_code == 401


# ── anti-fraud & RBAC at the API boundary ─────────────────────────────────────
def _bearer(api_client, user):
    from rest_framework_simplejwt.tokens import RefreshToken

    access = RefreshToken.for_user(user).access_token
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api_client


def test_stamp_daily_cap_returns_429_rate_limited(
    auth_client, customer_card, no_cooldown, monkeypatch
):
    """The per-card daily cap (a different guard than cooldown) surfaces as
    RATE_LIMITED through the envelope, not COOLDOWN_ACTIVE."""
    from core import constants

    monkeypatch.setattr(constants, "MAX_STAMPS_PER_CARD_PER_DAY", 2)
    for _ in range(2):
        ok = auth_client.post(STAMP_URL, {"customer_card_id": str(customer_card.id)}, format="json")
        assert ok.status_code == 200
    blocked = auth_client.post(
        STAMP_URL, {"customer_card_id": str(customer_card.id)}, format="json"
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"


def test_scanner_role_can_stamp(api_client, customer_card, merchant):
    """Scanner is the committed minimum role — prove it actually works."""
    from core.enums import Role

    scanner = factories.StaffUserFactory(merchant=merchant, role=Role.SCANNER)
    client = _bearer(api_client, scanner.user)
    resp = client.post(STAMP_URL, {"customer_card_id": str(customer_card.id)}, format="json")
    assert resp.status_code == 200


def test_authenticated_non_staff_is_forbidden(api_client, customer_card):
    """An authenticated user with no StaffUser profile gets 403, not 200."""
    outsider = factories.UserFactory()
    client = _bearer(api_client, outsider)
    resp = client.post(STAMP_URL, {"customer_card_id": str(customer_card.id)}, format="json")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "PERMISSION_DENIED"
