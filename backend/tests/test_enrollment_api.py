"""Tests for the enrollment endpoints (contract §3.6 · Phase 1.1)."""

from __future__ import annotations

import pytest
from django.utils import timezone

from core.models import CustomerCard, StampLedger
from enrollment.tokens import issue_enrollment_token

pytestmark = pytest.mark.django_db


@pytest.fixture
def token(card):
    return issue_enrollment_token(card)


def test_get_landing_returns_program_details(api_client, card, token):
    resp = api_client.get(f"/api/v1/enroll/{token.token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["card_name"] == card.name
    assert body["reward_title"] == card.reward_title
    assert body["stamps_required"] == card.stamps_required
    assert body["merchant_name"] == card.merchant.name


def test_landing_shows_powered_by_without_custom_branding(api_client, card, token):
    # A trial merchant = Growth-level = has custom_branding, so it's white-label.
    # Force a non-branded plan: activate Starter (custom_branding off).
    from billing.services import activate_plan
    from core.enums import PlanTier

    activate_plan(card.merchant, PlanTier.STARTER)
    body = api_client.get(f"/api/v1/enroll/{token.token}").json()
    assert body["show_powered_by"] is True
    assert body["headline"] == ""


def test_landing_uses_custom_copy_and_hides_powered_by_when_branded(api_client, card, token):
    from accounts.services import settings_for
    from billing.services import activate_plan
    from core.enums import PlanTier

    activate_plan(card.merchant, PlanTier.GROWTH)  # custom_branding on
    s = settings_for(card.merchant)
    s.enroll_headline = "Welcome to Cairo Coffee ☕"
    s.enroll_tagline = "Collect stamps, earn free drinks."
    s.save()

    body = api_client.get(f"/api/v1/enroll/{token.token}").json()
    assert body["show_powered_by"] is False
    assert body["headline"] == "Welcome to Cairo Coffee ☕"
    assert body["tagline"] == "Collect stamps, earn free drinks."


# ── referrals ─────────────────────────────────────────────────────────────────
def _enroll(api_client, token, phone, ref=None):
    body = {"customer_phone": phone, "consent": True}
    if ref:
        body["ref"] = str(ref)
    return api_client.post(f"/api/v1/enroll/{token.token}", body, format="json")


def test_referral_grants_bonus_to_both(api_client, card, token):
    from enrollment.models import Referral

    card.referral_enabled = True
    card.save(update_fields=["referral_enabled"])
    referrer = CustomerCard.objects.create(
        card=card, merchant=card.merchant, customer_phone="+201000000001"
    )

    resp = _enroll(api_client, token, "+201000000002", ref=referrer.id)
    assert resp.status_code == 201
    assert resp.json()["stamp_count"] == 1  # referee got the welcome bonus
    assert resp.json()["referral_url"].endswith(f"?ref={resp.json()['customer_card_id']}")

    referrer.refresh_from_db()
    assert referrer.stamp_count == 1  # referrer got the bonus too
    assert Referral.objects.filter(referrer=referrer).count() == 1


def test_referral_ignored_when_card_disabled(api_client, card, token):
    from enrollment.models import Referral

    referrer = CustomerCard.objects.create(
        card=card, merchant=card.merchant, customer_phone="+201000000001"
    )
    resp = _enroll(api_client, token, "+201000000002", ref=referrer.id)
    assert resp.status_code == 201
    assert resp.json()["stamp_count"] == 0  # no bonus (referrals off)
    assert resp.json()["referral_url"] == ""
    referrer.refresh_from_db()
    assert referrer.stamp_count == 0
    assert not Referral.objects.exists()


def test_referral_bad_ref_is_noop(api_client, card, token):
    import uuid

    card.referral_enabled = True
    card.save(update_fields=["referral_enabled"])
    resp = _enroll(api_client, token, "+201000000002", ref=uuid.uuid4())
    assert resp.status_code == 201
    assert resp.json()["stamp_count"] == 0  # unknown referrer → no bonus


def test_get_landing_unknown_token_404(api_client):
    resp = api_client.get("/api/v1/enroll/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_get_landing_expired_token_410(api_client, card):
    tok = issue_enrollment_token(card)
    tok.expires_at = timezone.now() - timezone.timedelta(days=1)
    tok.save(update_fields=["expires_at"])
    resp = api_client.get(f"/api/v1/enroll/{tok.token}")
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_post_enroll_creates_card_and_ledger(api_client, card, token):
    resp = api_client.post(
        f"/api/v1/enroll/{token.token}",
        {"customer_phone": "+201234567890", "customer_name": "Sara", "consent": True},
        format="json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["stamp_count"] == 0
    assert body["stamps_required"] == card.stamps_required
    assert "customer_card_id" in body
    assert "apple_pass_url" in body and "google_save_url" in body

    cc = CustomerCard.objects.get(id=body["customer_card_id"])
    assert cc.customer_phone == "+201234567890"
    assert cc.customer_name == "Sara"
    assert cc.consent_at is not None
    assert cc.merchant_id == card.merchant_id
    # Opening ENROLL ledger row exists.
    assert StampLedger.objects.filter(customer_card=cc, event_type="ENROLL").count() == 1


def test_post_enroll_requires_consent(api_client, token):
    resp = api_client.post(
        f"/api/v1/enroll/{token.token}",
        {"customer_phone": "+201234567890", "consent": False},
        format="json",
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "consent" in body["error"]["fields"]


def test_post_enroll_rejects_bad_phone(api_client, token):
    resp = api_client.post(
        f"/api/v1/enroll/{token.token}",
        {"customer_phone": "abc", "consent": True},
        format="json",
    )
    assert resp.status_code == 400
    assert "customer_phone" in resp.json()["error"]["fields"]


def test_post_enroll_duplicate_phone_conflicts(api_client, card, token):
    payload = {"customer_phone": "+201234567890", "consent": True}
    first = api_client.post(f"/api/v1/enroll/{token.token}", payload, format="json")
    assert first.status_code == 201
    second = api_client.post(f"/api/v1/enroll/{token.token}", payload, format="json")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "ALREADY_ENROLLED"
    # Only one card created.
    assert CustomerCard.objects.filter(card=card, customer_phone="+201234567890").count() == 1


def test_post_enroll_normalizes_phone_spaces(api_client, token):
    resp = api_client.post(
        f"/api/v1/enroll/{token.token}",
        {"customer_phone": "+20 123 456 7890", "consent": True},
        format="json",
    )
    assert resp.status_code == 201
    assert CustomerCard.objects.filter(customer_phone="+201234567890").exists()
