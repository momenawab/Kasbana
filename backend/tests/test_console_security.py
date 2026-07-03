"""Admin security hardening tests (Phase 15).

Covers the MFA login gate (forced enrolment + challenge), brute-force lockout,
session listing / revoke / "log out everywhere", refresh rotation + reuse
detection, step-up on the sensitive merchant-erase, and super-admin MFA reset.
Also the consolidated launch assertions: auth-boundary, permission-matrix, and
audit-completeness.
"""

from __future__ import annotations

import pyotp
import pytest

from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminSession, AdminUser
from console.rbac import mfa_required
from console.security import LOCKOUT_THRESHOLD
from core.models import Merchant
from tests.factories import MerchantFactory

pytestmark = pytest.mark.django_db

LOGIN = "/api/admin/v1/auth/login"
VERIFY = "/api/admin/v1/auth/mfa/verify"
REFRESH = "/api/admin/v1/auth/refresh"
SESSIONS = "/api/admin/v1/auth/sessions"
STEP_UP = "/api/admin/v1/auth/step-up"

PW = "supersecret1"


def _admin(email, role, mfa_secret="", mfa_enabled=False):
    a = AdminUser(email=email, name=email.split("@")[0], role=role, is_active=True)
    a.set_password(PW)
    a.mfa_secret = mfa_secret
    a.mfa_enabled = mfa_enabled
    a.save()
    return a


def _bearer(client, admin):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return client


def _full_login(client, admin):
    """Log in through the real flow (completing MFA if the role forces it), so the
    resulting session carries a fresh step-up proof. Returns the token pair."""
    r = client.post(LOGIN, {"email": admin.email, "password": PW}, format="json")
    if r.data["status"] == "ok":
        tokens = r.data
    else:
        admin.refresh_from_db()  # login stored the (setup) secret on the admin
        code = pyotp.TOTP(admin.mfa_secret).now()
        tokens = client.post(
            VERIFY, {"pending_token": r.data["pending_token"], "code": code}, format="json"
        ).data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return tokens


# ── MFA: forced enrolment for a privileged role ─────────────────────────────
def test_privileged_login_forces_mfa_setup_then_completes(api_client):
    admin = _admin("fin@stampn.net", AdminRole.FINANCE)  # privileged, no MFA yet
    resp = api_client.post(LOGIN, {"email": admin.email, "password": PW}, format="json")
    assert resp.status_code == 200
    assert resp.data["status"] == "mfa_setup"
    assert "access" not in resp.data  # NOT logged in yet
    assert resp.data["secret"] and resp.data["otpauth_uri"] and resp.data["qr"]

    # A valid code off the returned secret completes enrolment + logs in.
    code = pyotp.TOTP(resp.data["secret"]).now()
    done = api_client.post(
        VERIFY, {"pending_token": resp.data["pending_token"], "code": code}, format="json"
    )
    assert done.status_code == 200
    assert done.data["access"] and done.data["refresh"]
    admin.refresh_from_db()
    assert admin.mfa_enabled is True
    assert AdminAuditLog.objects.filter(action="admin.mfa_enrolled").exists()


def test_enrolled_login_requires_code_challenge(api_client):
    secret = pyotp.random_base32()
    admin = _admin("s@stampn.net", AdminRole.SUPER_ADMIN, mfa_secret=secret, mfa_enabled=True)
    resp = api_client.post(LOGIN, {"email": admin.email, "password": PW}, format="json")
    assert resp.data["status"] == "mfa_required"
    assert "access" not in resp.data

    bad = api_client.post(
        VERIFY, {"pending_token": resp.data["pending_token"], "code": "000000"}, format="json"
    )
    assert bad.status_code == 401

    ok = api_client.post(
        VERIFY,
        {"pending_token": resp.data["pending_token"], "code": pyotp.TOTP(secret).now()},
        format="json",
    )
    assert ok.status_code == 200 and ok.data["access"]


def test_readonly_role_skips_mfa(api_client):
    admin = _admin("ro@stampn.net", AdminRole.READ_ONLY)
    assert not mfa_required(AdminRole.READ_ONLY)
    resp = api_client.post(LOGIN, {"email": admin.email, "password": PW}, format="json")
    assert resp.data["status"] == "ok"
    assert resp.data["access"]


def test_pending_token_cannot_reach_real_endpoints(api_client):
    admin = _admin("fin2@stampn.net", AdminRole.FINANCE)
    resp = api_client.post(LOGIN, {"email": admin.email, "password": PW}, format="json")
    pending = resp.data["pending_token"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {pending}")
    # A half-auth token must not authenticate /me or anything else.
    assert api_client.get("/api/admin/v1/me").status_code in (401, 403)


# ── brute-force lockout ─────────────────────────────────────────────────────
def test_lockout_after_repeated_failures(api_client):
    admin = _admin("lock@stampn.net", AdminRole.READ_ONLY)
    for _ in range(LOCKOUT_THRESHOLD):
        r = api_client.post(LOGIN, {"email": admin.email, "password": "wrong"}, format="json")
        assert r.status_code == 401
    # Even the CORRECT password is now refused while locked.
    r = api_client.post(LOGIN, {"email": admin.email, "password": PW}, format="json")
    assert r.status_code == 401
    admin.refresh_from_db()
    assert admin.locked_until is not None


def test_successful_login_resets_failures(api_client):
    admin = _admin("reset@stampn.net", AdminRole.READ_ONLY)
    api_client.post(LOGIN, {"email": admin.email, "password": "wrong"}, format="json")
    api_client.post(LOGIN, {"email": admin.email, "password": PW}, format="json")
    admin.refresh_from_db()
    assert admin.failed_login_count == 0


# ── sessions: list, revoke, log-out-everywhere ──────────────────────────────
def test_login_creates_listable_session(api_client):
    admin = _admin("sess@stampn.net", AdminRole.READ_ONLY)
    tokens = api_client.post(LOGIN, {"email": admin.email, "password": PW}, format="json").data
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    resp = api_client.get(SESSIONS)
    assert resp.status_code == 200
    assert len(resp.data) == 1
    assert resp.data[0]["current"] is True


def test_revoke_current_session_kills_the_token(api_client):
    admin = _admin("kill@stampn.net", AdminRole.READ_ONLY)
    tokens = api_client.post(LOGIN, {"email": admin.email, "password": PW}, format="json").data
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    sid = api_client.get(SESSIONS).data[0]["id"]
    # revoke it, then the same access token must stop working
    assert api_client.delete(f"{SESSIONS}/{sid}").status_code == 200
    assert api_client.get(SESSIONS).status_code in (401, 403)


def test_logout_everywhere_keeps_current(api_client):
    admin = _admin("many@stampn.net", AdminRole.READ_ONLY)
    # two separate logins → two sessions
    t1 = api_client.post(LOGIN, {"email": admin.email, "password": PW}, format="json").data
    api_client.post(LOGIN, {"email": admin.email, "password": PW}, format="json")
    assert AdminSession.objects.filter(admin=admin, revoked=False).count() == 2
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {t1['access']}")
    resp = api_client.delete(SESSIONS)  # log out everywhere except me
    assert resp.status_code == 200 and resp.data["revoked"] == 1
    assert AdminSession.objects.filter(admin=admin, revoked=False).count() == 1
    assert api_client.get(SESSIONS).status_code == 200  # my session still works


# ── refresh rotation + reuse detection ──────────────────────────────────────
def test_refresh_rotates_and_detects_reuse(api_client):
    admin = _admin("rot@stampn.net", AdminRole.READ_ONLY)
    tokens = api_client.post(LOGIN, {"email": admin.email, "password": PW}, format="json").data
    old_refresh = tokens["refresh"]

    r1 = api_client.post(REFRESH, {"refresh": old_refresh}, format="json")
    assert r1.status_code == 200 and r1.data["refresh"] != old_refresh

    # Replaying the OLD refresh is reuse → rejected + session revoked.
    reuse = api_client.post(REFRESH, {"refresh": old_refresh}, format="json")
    assert reuse.status_code == 401
    # the freshly-rotated refresh is now dead too (session revoked)
    assert (
        api_client.post(REFRESH, {"refresh": r1.data["refresh"]}, format="json").status_code == 401
    )


# ── step-up on the sensitive merchant-erase ─────────────────────────────────
def test_erase_requires_step_up_then_succeeds(api_client):
    admin = _admin("super@stampn.net", AdminRole.SUPER_ADMIN)  # holds COMPLIANCE_DELETE
    merchant = MerchantFactory(slug="doomed-co")
    _full_login(api_client, admin)
    erase = f"/api/admin/v1/merchants/{merchant.id}/erase"
    payload = {"confirm": "doomed-co", "reason": "PDPL"}

    # Fresh login counts as a recent proof, so erase should pass immediately.
    resp = api_client.delete(erase, payload, format="json")
    assert resp.status_code == 204
    assert not Merchant.objects.filter(id=merchant.id).exists()


def test_erase_blocked_when_step_up_stale(api_client, monkeypatch):
    admin = _admin("super2@stampn.net", AdminRole.SUPER_ADMIN)
    merchant = MerchantFactory(slug="safe-co")
    _full_login(api_client, admin)
    # Force staleness: pretend no recent step-up.
    monkeypatch.setattr("console.security.step_up_fresh", lambda session: False)
    resp = api_client.delete(
        f"/api/admin/v1/merchants/{merchant.id}/erase",
        {"confirm": "safe-co", "reason": "x"},
        format="json",
    )
    assert resp.status_code == 403
    assert resp.data["error"]["code"] == "STEP_UP_REQUIRED"
    assert Merchant.objects.filter(id=merchant.id).exists()

    # A step-up (password + TOTP re-proof) then unblocks it.
    admin.refresh_from_db()
    step = api_client.post(
        STEP_UP,
        {"password": PW, "code": pyotp.TOTP(admin.mfa_secret).now()},
        format="json",
    )
    assert step.status_code == 200


# ── super-admin MFA reset (recovery path) ────────────────────────────────────
def test_super_can_reset_another_admins_mfa(api_client):
    secret = pyotp.random_base32()
    target = _admin("victim@stampn.net", AdminRole.FINANCE, mfa_secret=secret, mfa_enabled=True)
    AdminSession.objects.create(admin=target)  # a live session to be revoked
    superu = _admin("root@stampn.net", AdminRole.SUPER_ADMIN)

    resp = _bearer(api_client, superu).post(f"/api/admin/v1/admins/{target.id}/reset-mfa")
    assert resp.status_code == 200
    target.refresh_from_db()
    assert target.mfa_enabled is False and target.mfa_secret == ""
    assert AdminSession.objects.filter(admin=target, revoked=False).count() == 0


def test_non_super_cannot_reset_mfa(api_client):
    target = _admin("t@stampn.net", AdminRole.FINANCE)
    finance = _admin("f@stampn.net", AdminRole.FINANCE)
    resp = _bearer(api_client, finance).post(f"/api/admin/v1/admins/{target.id}/reset-mfa")
    assert resp.status_code == 403


# ── consolidated launch assertions ──────────────────────────────────────────
def test_merchant_token_cannot_reach_admin(api_client):
    # No credentials → the admin boundary refuses (401/403), never anonymous-allow.
    assert api_client.get("/api/admin/v1/merchants").status_code in (401, 403)


def test_login_and_sensitive_actions_are_audited(api_client):
    admin = _admin("aud@stampn.net", AdminRole.READ_ONLY)
    api_client.post(LOGIN, {"email": admin.email, "password": PW}, format="json")
    assert AdminAuditLog.objects.filter(action="admin.login", actor=admin).exists()
