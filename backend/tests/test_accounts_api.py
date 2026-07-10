"""Tests for the account-lifecycle endpoints (Phase 1.5 · contract Auth/Account/Settings).

Covers signup→trial, password recovery, staff-invite accept, /me session context
(trial vs paid wire enums), and business/account settings round-trips.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from accounts.models import MerchantSettings, PasswordResetToken, StaffInvite
from billing.plans import BillingStatus
from billing.services import activate_plan, lock, subscription_for
from core.enums import PlanTier, Role
from core.models import Merchant, StaffUser
from tests import factories

pytestmark = pytest.mark.django_db

SIGNUP = {
    "business_name": "Cairo Coffee",
    "owner_name": "Mona Owner",
    "email": "owner@cairocoffee.test",
    "phone": "+201000000000",
    "password": "supersecret",
    "consent": True,
}


def _auth(staff) -> APIClient:
    from rest_framework_simplejwt.tokens import RefreshToken

    client = APIClient()
    access = RefreshToken.for_user(staff.user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


# ── Signup ───────────────────────────────────────────────────────────────────
def test_signup_creates_merchant_owner_and_trial(api_client):
    resp = api_client.post("/api/v1/auth/signup", SIGNUP, format="json")
    assert resp.status_code == 200
    assert "access" in resp.json() and "refresh" in resp.json()

    merchant = Merchant.objects.get(name="Cairo Coffee")
    owner = StaffUser.objects.get(merchant=merchant)
    assert owner.role == Role.OWNER
    assert owner.user.email == SIGNUP["email"]
    # Trial started + settings seeded with the signup contact.
    assert subscription_for(merchant).status == BillingStatus.TRIALING
    s = MerchantSettings.objects.get(merchant=merchant)
    assert s.contact_phone == SIGNUP["phone"]


def test_signup_rejects_missing_consent(api_client):
    resp = api_client.post("/api/v1/auth/signup", {**SIGNUP, "consent": False}, format="json")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_signup_duplicate_email_409(api_client):
    api_client.post("/api/v1/auth/signup", SIGNUP, format="json")
    resp = api_client.post("/api/v1/auth/signup", SIGNUP, format="json")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


# ── Password recovery ─────────────────────────────────────────────────────────
def test_forgot_is_always_ok(api_client):
    factories.StaffUserFactory(user__email="known@x.test")
    assert (
        api_client.post("/api/v1/auth/forgot", {"email": "known@x.test"}, format="json").status_code
        == 200
    )
    # Unknown email also 200 (no enumeration), and issues no token.
    assert (
        api_client.post(
            "/api/v1/auth/forgot", {"email": "nobody@x.test"}, format="json"
        ).status_code
        == 200
    )
    assert PasswordResetToken.objects.filter(user__email="nobody@x.test").count() == 0


def test_forgot_ignores_email_notification_opt_out(api_client, merchant, mailoutbox):
    """`notif_email` gates broadcasts only — account recovery must always send."""
    staff = factories.StaffUserFactory(merchant=merchant, user__email="quiet@x.test")
    s = MerchantSettings.objects.create(merchant=staff.merchant, notif_email=False)
    assert s.notif_email is False

    api_client.post("/api/v1/auth/forgot", {"email": "quiet@x.test"}, format="json")
    assert len(mailoutbox) == 1
    assert PasswordResetToken.objects.filter(user__email="quiet@x.test").exists()


def test_reset_with_valid_token(api_client):
    staff = factories.StaffUserFactory(user__email="reset@x.test")
    reset = PasswordResetToken.objects.create(user=staff.user)
    resp = api_client.post(
        "/api/v1/auth/reset", {"token": reset.token, "password": "brandnewpass"}, format="json"
    )
    assert resp.status_code == 200
    staff.user.refresh_from_db()
    assert staff.user.check_password("brandnewpass")
    reset.refresh_from_db()
    assert reset.used_at is not None


def test_reset_with_invalid_token_410(api_client):
    resp = api_client.post(
        "/api/v1/auth/reset", {"token": "nope", "password": "brandnewpass"}, format="json"
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "TOKEN_EXPIRED"


# ── Invites ────────────────────────────────────────────────────────────────────
def test_invite_inspect_and_accept(api_client, merchant):
    invite = StaffInvite.objects.create(merchant=merchant, email="new@x.test", role=Role.SCANNER)

    info = api_client.get(f"/api/v1/auth/invite/{invite.token}")
    assert info.status_code == 200
    assert info.json() == {"merchant_name": merchant.name, "role": "SCANNER", "email": "new@x.test"}

    accept = api_client.post(
        f"/api/v1/auth/invite/{invite.token}", {"password": "joinmeup1"}, format="json"
    )
    assert accept.status_code == 200
    assert "access" in accept.json()
    staff = StaffUser.objects.get(user__email="new@x.test")
    assert staff.merchant_id == merchant.id and staff.role == Role.SCANNER
    invite.refresh_from_db()
    assert invite.accepted_at is not None


def test_invite_accept_is_single_use(api_client, merchant):
    invite = StaffInvite.objects.create(merchant=merchant, email="new@x.test", role=Role.ADMIN)
    api_client.post(f"/api/v1/auth/invite/{invite.token}", {"password": "joinmeup1"}, format="json")
    again = api_client.post(
        f"/api/v1/auth/invite/{invite.token}", {"password": "joinmeup1"}, format="json"
    )
    assert again.status_code == 410


# ── /me ────────────────────────────────────────────────────────────────────────
def test_me_for_trial_merchant(merchant):
    staff = factories.StaffUserFactory(merchant=merchant, role=Role.OWNER)
    resp = _auth(staff).get("/api/v1/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["staff"]["role"] == "OWNER"
    assert body["merchant"]["plan"] == "trial"
    assert body["merchant"]["status"] == "trial"
    ent = body["entitlements"]
    # Trial gives Growth-level limits/features.
    assert ent["plan"] == "trial"
    assert ent["limits"]["max_cards"] == 10
    assert ent["features"]["api"] is True
    assert ent["features"]["analytics"] == "full"
    assert ent["usage"]["cards"] == 0


def test_me_for_paid_starter_merchant(merchant):
    activate_plan(merchant, PlanTier.STARTER)
    staff = factories.StaffUserFactory(merchant=merchant, role=Role.ADMIN)
    body = _auth(staff).get("/api/v1/me").json()
    assert body["merchant"]["plan"] == "starter"
    assert body["merchant"]["status"] == "active"
    assert body["entitlements"]["features"]["api"] is False


def test_me_requires_auth(api_client):
    assert api_client.get("/api/v1/me").status_code in (401, 403)


# ── Settings ─────────────────────────────────────────────────────────────────
def test_business_settings_round_trip(merchant):
    staff = factories.StaffUserFactory(merchant=merchant, role=Role.ADMIN)
    client = _auth(staff)

    resp = client.patch(
        "/api/v1/settings/business",
        {
            "name": "Renamed Co",
            "color_bg": "#112233",
            "contact": {"phone": "+201111111111"},
            "address": "5 Tahrir St",
        },
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Co"

    merchant.refresh_from_db()
    assert merchant.name == "Renamed Co" and merchant.color_bg == "#112233"
    s = MerchantSettings.objects.get(merchant=merchant)
    assert s.contact_phone == "+201111111111" and s.address == "5 Tahrir St"


# The dashboard Business tab always posts every field it renders, including the
# two custom_branding-gated enroll fields (blank when the plan can't set them).
# Gating on key *presence* used to 402 the whole save on Starter.
def _business_tab_payload(**over):
    return {
        "name": "Renamed Co",
        "color_bg": "#0E1B2A",
        "color_fg": "#FFFFFF",
        "enroll_headline": "",
        "enroll_tagline": "",
        "contact": {"phone": "+201111111111"},
        **over,
    }


def test_business_save_with_blank_enroll_copy_is_ungated(merchant):
    staff = factories.StaffUserFactory(merchant=merchant, role=Role.ADMIN)
    activate_plan(merchant, PlanTier.STARTER)  # custom_branding off

    resp = _auth(staff).patch("/api/v1/settings/business", _business_tab_payload(), format="json")
    assert resp.status_code == 200
    merchant.refresh_from_db()
    assert merchant.name == "Renamed Co"


def test_business_save_resending_stored_enroll_copy_is_ungated(merchant):
    """A downgraded merchant reloads the tab, which echoes the stored copy back."""
    staff = factories.StaffUserFactory(merchant=merchant, role=Role.ADMIN)
    s = MerchantSettings.objects.create(merchant=merchant, enroll_headline="Kept")
    activate_plan(merchant, PlanTier.STARTER)

    resp = _auth(staff).patch(
        "/api/v1/settings/business",
        _business_tab_payload(enroll_headline="Kept"),
        format="json",
    )
    assert resp.status_code == 200
    s.refresh_from_db()
    assert s.enroll_headline == "Kept"


def test_business_save_can_clear_enroll_copy_after_downgrade(merchant):
    staff = factories.StaffUserFactory(merchant=merchant, role=Role.ADMIN)
    s = MerchantSettings.objects.create(merchant=merchant, enroll_headline="Old")
    activate_plan(merchant, PlanTier.STARTER)

    resp = _auth(staff).patch("/api/v1/settings/business", _business_tab_payload(), format="json")
    assert resp.status_code == 200
    s.refresh_from_db()
    assert s.enroll_headline == ""


def test_business_save_setting_enroll_copy_still_requires_branding(merchant):
    staff = factories.StaffUserFactory(merchant=merchant, role=Role.ADMIN)
    activate_plan(merchant, PlanTier.STARTER)
    original_name = merchant.name

    resp = _auth(staff).patch(
        "/api/v1/settings/business",
        _business_tab_payload(enroll_headline="Join us!"),
        format="json",
    )
    assert resp.status_code == 402
    # The rejected save must not half-apply the ungated fields.
    merchant.refresh_from_db()
    assert merchant.name == original_name


def test_business_save_setting_enroll_copy_allowed_on_growth(merchant):
    staff = factories.StaffUserFactory(merchant=merchant, role=Role.ADMIN)
    activate_plan(merchant, PlanTier.GROWTH)  # custom_branding on

    resp = _auth(staff).patch(
        "/api/v1/settings/business",
        _business_tab_payload(enroll_headline="Join us!"),
        format="json",
    )
    assert resp.status_code == 200
    assert MerchantSettings.objects.get(merchant=merchant).enroll_headline == "Join us!"


def test_business_settings_requires_admin(merchant):
    scanner = factories.StaffUserFactory(merchant=merchant, role=Role.SCANNER)
    resp = _auth(scanner).patch("/api/v1/settings/business", {"name": "X"}, format="json")
    assert resp.status_code == 403


def test_account_settings_round_trip(merchant):
    staff = factories.StaffUserFactory(merchant=merchant, role=Role.SCANNER)
    client = _auth(staff)

    assert client.get("/api/v1/settings/account").json()["language"] == "ar"
    resp = client.patch(
        "/api/v1/settings/account",
        {"language": "en", "notifications": {"whatsapp": True}},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["language"] == "en"
    assert body["notifications"]["whatsapp"] is True


def test_password_change(merchant):
    staff = factories.StaffUserFactory(merchant=merchant)
    staff.user.set_password("oldpassword")
    staff.user.save()
    client = _auth(staff)

    bad = client.post(
        "/api/v1/settings/account/password",
        {"current": "wrongpass", "new": "newpassword"},
        format="json",
    )
    assert bad.status_code == 400

    ok = client.post(
        "/api/v1/settings/account/password",
        {"current": "oldpassword", "new": "newpassword"},
        format="json",
    )
    assert ok.status_code == 200
    staff.user.refresh_from_db()
    assert staff.user.check_password("newpassword")
    # Re-issues a fresh token pair for the current device.
    assert ok.json()["access"] and ok.json()["refresh"]


def test_password_change_revokes_existing_refresh_tokens(merchant):
    """An old session's refresh token stops working after a password change; the
    fresh pair returned to the caller keeps working."""
    from rest_framework_simplejwt.tokens import RefreshToken

    staff = factories.StaffUserFactory(merchant=merchant)
    staff.user.set_password("oldpassword")
    staff.user.save()

    old_refresh = str(RefreshToken.for_user(staff.user))  # a pre-existing session
    resp = _auth(staff).post(
        "/api/v1/settings/account/password",
        {"current": "oldpassword", "new": "newpassword"},
        format="json",
    )
    assert resp.status_code == 200

    # The old session can no longer refresh...
    assert (
        APIClient()
        .post("/api/v1/auth/refresh", {"refresh": old_refresh}, format="json")
        .status_code
        == 401
    )
    # ...but the freshly-issued one can.
    new_refresh = resp.json()["refresh"]
    assert (
        APIClient()
        .post("/api/v1/auth/refresh", {"refresh": new_refresh}, format="json")
        .status_code
        == 200
    )


# ── Account data export (PDPL) ────────────────────────────────────────────────
def test_account_export_owner_gets_full_snapshot(merchant):
    owner = factories.StaffUserFactory(merchant=merchant, role=Role.OWNER)
    factories.StaffUserFactory(merchant=merchant, role=Role.SCANNER)
    MerchantSettings.objects.create(merchant=merchant, contact_phone="+201234567890")

    resp = _auth(owner).get("/api/v1/settings/account/export")
    assert resp.status_code == 200
    assert 'attachment; filename="stampn-' in resp["Content-Disposition"]
    body = resp.json()
    assert body["merchant"]["id"] == str(merchant.id)
    assert body["settings"]["contact_phone"] == "+201234567890"
    assert {s["role"] for s in body["staff"]} == {Role.OWNER, Role.SCANNER}
    assert "exported_at" in body


def test_account_export_is_owner_only(merchant):
    admin = factories.StaffUserFactory(merchant=merchant, role=Role.ADMIN)
    assert _auth(admin).get("/api/v1/settings/account/export").status_code == 403


def test_account_export_is_tenant_scoped(merchant):
    """One owner never sees another merchant's staff/data."""
    owner = factories.StaffUserFactory(merchant=merchant, role=Role.OWNER)
    other = factories.MerchantFactory(name="Rival")
    factories.StaffUserFactory(merchant=other, role=Role.OWNER, user__email="rival@x.test")

    body = _auth(owner).get("/api/v1/settings/account/export").json()
    emails = {s["email"] for s in body["staff"]}
    assert "rival@x.test" not in emails


def test_locked_merchant_me_shows_suspended(merchant):
    lock(merchant)
    staff = factories.StaffUserFactory(merchant=merchant, role=Role.OWNER)
    body = _auth(staff).get("/api/v1/me").json()
    assert body["merchant"]["status"] == "suspended"
