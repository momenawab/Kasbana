"""Compliance tools tests (Phase 13, PDPL).

Covers super-admin-only gating on export + delete, the typed-slug confirmation,
the cascade erase with a pre-delete audit snapshot, consent-record reads (any
admin), and the retention policy read/write (read any admin, write super-only).
"""

from __future__ import annotations

import pytest

from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser, RetentionPolicy
from core.models import CustomerCard, Merchant
from tests.factories import CustomerCardFactory, MerchantFactory

pytestmark = pytest.mark.django_db

RETENTION = "/api/admin/v1/compliance/retention"


def _admin(email, role):
    a = AdminUser(email=email, name=email.split("@")[0], role=role, is_active=True)
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
def readonly_admin():
    return _admin("readonly@stampn.net", AdminRole.READ_ONLY)


def _bearer(client, admin):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return client


@pytest.fixture
def merchant_with_data():
    merchant = MerchantFactory(slug="acme-coffee")
    CustomerCardFactory(merchant=merchant, customer_phone="+201000000001")
    CustomerCardFactory(merchant=merchant, customer_phone="+201000000002")
    return merchant


# ── data export ─────────────────────────────────────────────────────────────
def test_super_can_export_merchant_bundle(api_client, super_admin, merchant_with_data):
    resp = _bearer(api_client, super_admin).get(
        f"/api/admin/v1/merchants/{merchant_with_data.id}/export"
    )
    assert resp.status_code == 200
    assert "attachment" in resp["Content-Disposition"]
    assert resp.data["merchant"]["slug"] == "acme-coffee"
    assert len(resp.data["customers"]) == 2
    # audited (export carries PII)
    assert AdminAuditLog.objects.filter(action="merchant.data_export").count() == 1


def test_non_super_cannot_export(api_client, finance_admin, merchant_with_data):
    resp = _bearer(api_client, finance_admin).get(
        f"/api/admin/v1/merchants/{merchant_with_data.id}/export"
    )
    assert resp.status_code == 403
    assert not AdminAuditLog.objects.filter(action="merchant.data_export").exists()


# ── right-to-be-forgotten delete ─────────────────────────────────────────────
def _erase(merchant_id):
    return f"/api/admin/v1/merchants/{merchant_id}/erase"


def test_super_can_erase_merchant_with_typed_confirm(api_client, super_admin, merchant_with_data):
    mid = merchant_with_data.id
    resp = _bearer(api_client, super_admin).delete(
        _erase(mid), {"confirm": "acme-coffee", "reason": "PDPL request"}, format="json"
    )
    assert resp.status_code == 204
    assert not Merchant.objects.filter(id=mid).exists()
    assert CustomerCard.objects.filter(merchant_id=mid).count() == 0  # cascaded
    # audited BEFORE the cascade, with the counts snapshot + reason
    log = AdminAuditLog.objects.get(action="merchant.delete")
    assert log.metadata["reason"] == "PDPL request"
    assert log.metadata["counts"]["customers"] == 2


def test_wrong_confirm_does_not_delete(api_client, super_admin, merchant_with_data):
    resp = _bearer(api_client, super_admin).delete(
        _erase(merchant_with_data.id), {"confirm": "wrong", "reason": "x"}, format="json"
    )
    assert resp.status_code == 409
    assert resp.data["error"]["code"] == "CONFIRM_MISMATCH"
    assert Merchant.objects.filter(id=merchant_with_data.id).exists()
    assert not AdminAuditLog.objects.filter(action="merchant.delete").exists()


def test_non_super_cannot_erase(api_client, finance_admin, merchant_with_data):
    resp = _bearer(api_client, finance_admin).delete(
        _erase(merchant_with_data.id),
        {"confirm": "acme-coffee", "reason": "x"},
        format="json",
    )
    assert resp.status_code == 403
    assert Merchant.objects.filter(id=merchant_with_data.id).exists()


# ── consent records ──────────────────────────────────────────────────────────
def test_any_admin_can_read_consent(api_client, readonly_admin, merchant_with_data):
    resp = _bearer(api_client, readonly_admin).get(
        f"/api/admin/v1/merchants/{merchant_with_data.id}/consent"
    )
    assert resp.status_code == 200
    assert len(resp.data) == 2
    assert {"customer_phone", "consent_at", "status"} <= set(resp.data[0].keys())


# ── retention policy ─────────────────────────────────────────────────────────
def test_retention_read_open_to_any_admin_with_defaults(api_client, readonly_admin):
    resp = _bearer(api_client, readonly_admin).get(RETENTION)
    assert resp.status_code == 200
    assert resp.data["inactive_customer_days"] == 0  # 0 = keep indefinitely


def test_super_can_update_retention(api_client, super_admin):
    resp = _bearer(api_client, super_admin).patch(
        RETENTION, {"inactive_customer_days": 365, "audit_log_days": 730}, format="json"
    )
    assert resp.status_code == 200
    assert resp.data["inactive_customer_days"] == 365
    assert resp.data["updated_by_email"] == "super@stampn.net"
    assert RetentionPolicy.current().audit_log_days == 730
    log = AdminAuditLog.objects.get(action="retention.update")
    assert log.metadata["after"]["inactive_customer_days"] == 365


def test_non_super_cannot_update_retention(api_client, finance_admin):
    resp = _bearer(api_client, finance_admin).patch(
        RETENTION, {"inactive_customer_days": 365}, format="json"
    )
    assert resp.status_code == 403


def test_negative_retention_rejected(api_client, super_admin):
    resp = _bearer(api_client, super_admin).patch(
        RETENTION, {"inactive_customer_days": -1}, format="json"
    )
    assert resp.status_code == 400
