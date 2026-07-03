"""Admin-team management + RBAC matrix tests (Phase 12).

Covers the central matrix (single source of truth), the admin-only management
endpoints (invite/list/patch/activity), the last-super-admin guardrail, and the
DoD role separations (Support can't edit plans; Read-only can't mutate anything).
"""

from __future__ import annotations

import pytest

from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser
from console.rbac import ALL_PERMISSIONS, Permission, mfa_required, permissions_for, role_can

pytestmark = pytest.mark.django_db

ADMINS = "/api/admin/v1/admins"


def _admin(email, role, active=True):
    a = AdminUser(email=email, name=email.split("@")[0], role=role, is_active=active)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def super_admin():
    return _admin("super@stampn.net", AdminRole.SUPER_ADMIN)


@pytest.fixture
def finance_admin():
    return _admin("finance@stampn.net", AdminRole.FINANCE)


@pytest.fixture
def support_admin():
    return _admin("support@stampn.net", AdminRole.SUPPORT)


@pytest.fixture
def readonly_admin():
    return _admin("readonly@stampn.net", AdminRole.READ_ONLY)


def _bearer(client, admin):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return client


# ── matrix (source of truth) ────────────────────────────────────────────────
def test_super_admin_holds_every_permission():
    assert permissions_for(AdminRole.SUPER_ADMIN) == ALL_PERMISSIONS


def test_finance_holds_finance_bucket_only():
    perms = permissions_for(AdminRole.FINANCE)
    assert Permission.PLANS_MANAGE in perms
    assert Permission.BILLING_MANAGE in perms
    assert Permission.SUPPORT_TOOLS not in perms
    assert Permission.ADMINS_MANAGE not in perms


def test_readonly_holds_nothing_engineering_holds_ops():
    assert permissions_for(AdminRole.READ_ONLY) == frozenset()
    # Engineering's only permission is platform ops (Phase 14).
    assert permissions_for(AdminRole.ENGINEERING) == frozenset({Permission.OPS_MANAGE})


def test_only_super_admin_can_manage_admins():
    assert role_can(AdminRole.SUPER_ADMIN, Permission.ADMINS_MANAGE)
    for role in (
        AdminRole.FINANCE,
        AdminRole.SUPPORT,
        AdminRole.MARKETING_ADMIN,
        AdminRole.ENGINEERING,
        AdminRole.READ_ONLY,
    ):
        assert not role_can(role, Permission.ADMINS_MANAGE)


def test_mfa_required_for_privileged_roles_only():
    assert mfa_required(AdminRole.SUPER_ADMIN)
    assert mfa_required(AdminRole.FINANCE)
    # Engineering holds OPS_MANAGE since Phase 14, so it is now privileged too.
    assert mfa_required(AdminRole.ENGINEERING)
    assert not mfa_required(AdminRole.READ_ONLY)


# ── DoD: role separation still enforced on real endpoints ───────────────────
def test_support_admin_cannot_edit_plans(api_client, support_admin):
    resp = _bearer(api_client, support_admin).post(
        "/api/admin/v1/plans", {"key": "X", "name": "X", "price_egp": "1"}, format="json"
    )
    assert resp.status_code == 403


def test_readonly_admin_cannot_mutate_anything(api_client, readonly_admin):
    client = _bearer(api_client, readonly_admin)
    # a representative mutation from each gated domain
    assert client.post("/api/admin/v1/plans", {}, format="json").status_code == 403
    assert (
        client.patch("/api/admin/v1/plans/GROWTH", {"price_egp": "1"}, format="json").status_code
        == 403
    )


# ── admin management: role gate ─────────────────────────────────────────────
def test_non_super_cannot_list_or_invite_admins(api_client, finance_admin):
    client = _bearer(api_client, finance_admin)
    assert client.get(ADMINS).status_code == 403
    assert (
        client.post(ADMINS, {"email": "x@stampn.net", "role": "SUPPORT"}, format="json").status_code
        == 403
    )


def test_super_admin_can_list_admins(api_client, super_admin, finance_admin):
    resp = _bearer(api_client, super_admin).get(ADMINS)
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()}
    assert {"super@stampn.net", "finance@stampn.net"} <= emails
    # each row carries the derived permission set + mfa flag
    finance_row = next(r for r in resp.json() if r["email"] == "finance@stampn.net")
    assert Permission.BILLING_MANAGE in finance_row["permissions"]
    assert finance_row["mfa_required"] is True


# ── invite ──────────────────────────────────────────────────────────────────
def test_invite_creates_admin_with_temp_password(api_client, super_admin):
    resp = _bearer(api_client, super_admin).post(
        ADMINS, {"email": "New@Stampn.net", "name": "New", "role": "SUPPORT"}, format="json"
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["temporary_password"]
    assert body["admin"]["email"] == "new@stampn.net"  # normalised
    created = AdminUser.objects.get(email="new@stampn.net")
    assert created.check_password(body["temporary_password"])  # usable immediately
    assert AdminAuditLog.objects.filter(action="admin.invite", target_id=str(created.id)).exists()


def test_invite_rejects_duplicate_email(api_client, super_admin, finance_admin):
    resp = _bearer(api_client, super_admin).post(
        ADMINS, {"email": "finance@stampn.net", "role": "SUPPORT"}, format="json"
    )
    assert resp.status_code == 409


# ── patch: role / active + guards ───────────────────────────────────────────
def test_super_can_change_another_admins_role(api_client, super_admin, support_admin):
    resp = _bearer(api_client, super_admin).patch(
        f"{ADMINS}/{support_admin.id}", {"role": "FINANCE", "reason": "moved teams"}, format="json"
    )
    assert resp.status_code == 200
    support_admin.refresh_from_db()
    assert support_admin.role == AdminRole.FINANCE
    log = AdminAuditLog.objects.get(action="admin.update", target_id=str(support_admin.id))
    assert log.metadata["before"]["role"] == "SUPPORT"
    assert log.metadata["after"]["role"] == "FINANCE"


def test_patch_requires_reason(api_client, super_admin, support_admin):
    resp = _bearer(api_client, super_admin).patch(
        f"{ADMINS}/{support_admin.id}", {"is_active": False}, format="json"
    )
    assert resp.status_code == 400


def test_can_deactivate_another_admin(api_client, super_admin, support_admin):
    resp = _bearer(api_client, super_admin).patch(
        f"{ADMINS}/{support_admin.id}",
        {"is_active": False, "reason": "left company"},
        format="json",
    )
    assert resp.status_code == 200
    support_admin.refresh_from_db()
    assert support_admin.is_active is False


def test_cannot_demote_the_last_active_super_admin(api_client, super_admin):
    """super_admin is the only active super — demoting them (even by themselves)
    would lock the platform out of admin management, so it's blocked."""
    resp = _bearer(api_client, super_admin).patch(
        f"{ADMINS}/{super_admin.id}", {"role": "FINANCE", "reason": "oops"}, format="json"
    )
    assert resp.status_code == 409
    super_admin.refresh_from_db()
    assert super_admin.role == AdminRole.SUPER_ADMIN  # unchanged


def test_cannot_deactivate_the_last_active_super_admin(api_client, super_admin):
    resp = _bearer(api_client, super_admin).patch(
        f"{ADMINS}/{super_admin.id}", {"is_active": False, "reason": "x"}, format="json"
    )
    assert resp.status_code == 409


def test_can_demote_a_super_when_another_active_super_remains(api_client, super_admin):
    other_super = _admin("super2@stampn.net", AdminRole.SUPER_ADMIN)
    resp = _bearer(api_client, super_admin).patch(
        f"{ADMINS}/{other_super.id}", {"role": "FINANCE", "reason": "consolidate"}, format="json"
    )
    assert resp.status_code == 200
    other_super.refresh_from_db()
    assert other_super.role == AdminRole.FINANCE


# ── activity + matrix reference ─────────────────────────────────────────────
def test_admin_activity_lists_that_admins_actions(api_client, super_admin, support_admin):
    # The endpoint reads AdminAuditLog filtered by actor; seed one row for support.
    AdminAuditLog.objects.create(
        actor=support_admin, actor_email=support_admin.email, action="support.note"
    )
    resp = _bearer(api_client, super_admin).get(f"{ADMINS}/{support_admin.id}/activity")
    assert resp.status_code == 200
    assert [r["action"] for r in resp.json()] == ["support.note"]


def test_rbac_matrix_is_readable_by_any_admin(api_client, readonly_admin):
    resp = _bearer(api_client, readonly_admin).get("/api/admin/v1/rbac/matrix")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["permissions"]) == set(ALL_PERMISSIONS)
    super_row = next(r for r in body["roles"] if r["role"] == "SUPER_ADMIN")
    assert set(super_row["permissions"]) == set(ALL_PERMISSIONS)
    assert super_row["mfa_required"] is True


def test_me_now_reports_permissions_and_mfa_required(api_client, finance_admin):
    resp = _bearer(api_client, finance_admin).get("/api/admin/v1/me")
    assert resp.status_code == 200
    assert Permission.BILLING_MANAGE in resp.json()["permissions"]
    assert resp.json()["mfa_required"] is True
