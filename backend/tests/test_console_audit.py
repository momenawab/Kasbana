"""Audit-log viewer tests (Phase 13).

Covers the filter matrix, the any-admin read convention (a Read-only admin can
audit the platform), the paginated list shape, and the CSV export.
"""

from __future__ import annotations

import pytest

from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser

pytestmark = pytest.mark.django_db

AUDIT = "/api/admin/v1/audit"


def _admin(email, role):
    a = AdminUser(email=email, name=email.split("@")[0], role=role, is_active=True)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def super_admin():
    return _admin("super@stampn.net", AdminRole.SUPER_ADMIN)


@pytest.fixture
def readonly_admin():
    return _admin("readonly@stampn.net", AdminRole.READ_ONLY)


def _bearer(client, admin):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return client


@pytest.fixture
def events(super_admin):
    AdminAuditLog.objects.create(
        actor=super_admin,
        actor_email=super_admin.email,
        action="merchant.suspend",
        target_type="merchant",
        target_id="m-1",
        metadata={"reason": "spam"},
    )
    AdminAuditLog.objects.create(
        actor=super_admin,
        actor_email="finance@stampn.net",
        action="invoice.retry",
        target_type="invoice",
        target_id="i-9",
    )
    return AdminAuditLog.objects.count()


def test_list_returns_paginated_events(api_client, super_admin, events):
    resp = _bearer(api_client, super_admin).get(AUDIT)
    assert resp.status_code == 200
    assert "results" in resp.data
    assert len(resp.data["results"]) == events


def test_readonly_admin_can_view_audit(api_client, readonly_admin, events):
    # Reads stay open to any active admin — auditing is precisely Read-only's job.
    resp = _bearer(api_client, readonly_admin).get(AUDIT)
    assert resp.status_code == 200
    assert len(resp.data["results"]) == events


def test_filter_by_action(api_client, super_admin, events):
    resp = _bearer(api_client, super_admin).get(AUDIT, {"action": "suspend"})
    assert resp.status_code == 200
    assert [e["action"] for e in resp.data["results"]] == ["merchant.suspend"]


def test_filter_by_actor_email(api_client, super_admin, events):
    resp = _bearer(api_client, super_admin).get(AUDIT, {"actor": "finance@"})
    assert [e["action"] for e in resp.data["results"]] == ["invoice.retry"]


def test_filter_by_target(api_client, super_admin, events):
    resp = _bearer(api_client, super_admin).get(
        AUDIT, {"target_type": "merchant", "target_id": "m-1"}
    )
    assert len(resp.data["results"]) == 1
    assert resp.data["results"][0]["metadata"]["reason"] == "spam"


def test_export_is_csv(api_client, super_admin, events):
    resp = _bearer(api_client, super_admin).get(f"{AUDIT}/export")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert "attachment" in resp["Content-Disposition"]
    body = resp.content.decode()
    assert "actor_email,action" in body
    assert "merchant.suspend" in body


def test_requires_admin_auth(api_client):
    assert api_client.get(AUDIT).status_code in (401, 403)
