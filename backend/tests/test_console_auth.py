"""Admin console auth-boundary tests (Phase 1).

The security-critical assertions: an admin can log in and reach ``/me``, a
merchant JWT is REJECTED by admin endpoints, and an admin JWT is REJECTED by
merchant endpoints. Plus login failure + refresh.
"""

from __future__ import annotations

import pytest

from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser
from tests import factories

pytestmark = pytest.mark.django_db

LOGIN = "/api/admin/v1/auth/login"
ME = "/api/admin/v1/me"


@pytest.fixture
def admin_user():
    admin = AdminUser(email="ops@stampn.net", name="Ops", role=AdminRole.SUPER_ADMIN)
    admin.set_password("supersecret1")
    admin.save()
    return admin


def _bearer(client, token):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


# ── login ─────────────────────────────────────────────────────────────────────
def test_admin_login_succeeds_and_returns_tokens(api_client, admin_user):
    resp = api_client.post(
        LOGIN, {"email": "ops@stampn.net", "password": "supersecret1"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["access"] and resp.json()["refresh"]
    # Login is audited.
    assert AdminAuditLog.objects.filter(action="admin.login", actor=admin_user).exists()


def test_admin_login_bad_password_401(api_client, admin_user):
    resp = api_client.post(LOGIN, {"email": "ops@stampn.net", "password": "wrong"}, format="json")
    assert resp.status_code == 401


def test_admin_login_unknown_email_401(api_client):
    resp = api_client.post(
        LOGIN, {"email": "nobody@stampn.net", "password": "whatever1"}, format="json"
    )
    assert resp.status_code == 401


def test_inactive_admin_cannot_login(api_client, admin_user):
    admin_user.is_active = False
    admin_user.save(update_fields=["is_active"])
    resp = api_client.post(
        LOGIN, {"email": "ops@stampn.net", "password": "supersecret1"}, format="json"
    )
    assert resp.status_code == 401


# ── /me ───────────────────────────────────────────────────────────────────────
def test_admin_me_returns_profile(api_client, admin_user):
    access = issue_admin_tokens(admin_user)["access"]
    resp = _bearer(api_client, access).get(ME)
    assert resp.status_code == 200
    assert resp.json()["email"] == "ops@stampn.net"
    assert resp.json()["role"] == "SUPER_ADMIN"


def test_me_requires_auth(api_client):
    assert api_client.get(ME).status_code == 401


# ── the boundary (security-critical) ──────────────────────────────────────────
def test_merchant_token_is_rejected_by_admin_endpoint(api_client, merchant):
    """A valid MERCHANT JWT must NOT authenticate against an admin endpoint."""
    from rest_framework_simplejwt.tokens import RefreshToken

    staff = factories.StaffUserFactory(merchant=merchant)
    merchant_access = str(RefreshToken.for_user(staff.user).access_token)
    resp = _bearer(api_client, merchant_access).get(ME)
    assert resp.status_code in (401, 403)  # rejected — no admin realm


def test_admin_token_is_rejected_by_merchant_endpoint(api_client, admin_user):
    """An ADMIN JWT must NOT authenticate against a merchant endpoint."""
    admin_access = issue_admin_tokens(admin_user)["access"]
    resp = _bearer(api_client, admin_access).get("/api/v1/me")
    assert resp.status_code in (401, 403)


def test_admin_refresh_issues_new_access(api_client, admin_user):
    refresh = issue_admin_tokens(admin_user)["refresh"]
    resp = api_client.post("/api/admin/v1/auth/refresh", {"refresh": refresh}, format="json")
    assert resp.status_code == 200
    # The new access token works.
    assert _bearer(api_client, resp.json()["access"]).get(ME).status_code == 200
