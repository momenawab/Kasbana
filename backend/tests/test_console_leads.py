"""Inbound "Get started" lead tests.

Covers the public (unauthenticated) intake from the marketing site — including
validation and the bot honeypot — plus the admin console list / mark-contacted /
delete flow and its audit trail.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser, Lead

pytestmark = pytest.mark.django_db

PUBLIC = "/api/v1/leads"
ADMIN = "/api/admin/v1/leads"

VALID = {
    "name": "Ali Hassan",
    "email": "ali@bloomcafe.com",
    "phone": "01000000000",
    "business_name": "Bloom Café",
}


@pytest.fixture
def super_admin():
    a = AdminUser(email="super@stampn.net", role=AdminRole.SUPER_ADMIN)
    a.set_password("supersecret1")
    a.save()
    return a


def _admin(admin):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return c


# ── Public intake ───────────────────────────────────────────────────────────
def test_public_can_create_lead_without_auth():
    res = APIClient().post(PUBLIC, VALID, format="json")
    assert res.status_code == 201
    lead = Lead.objects.get()
    assert lead.business_name == "Bloom Café"
    assert lead.status == Lead.Status.NEW


def test_missing_fields_rejected():
    res = APIClient().post(PUBLIC, {"name": "Ali"}, format="json")
    assert res.status_code == 400
    assert Lead.objects.count() == 0


def test_honeypot_is_accepted_but_saves_nothing():
    res = APIClient().post(PUBLIC, {**VALID, "botcheck": "spam"}, format="json")
    assert res.status_code == 201
    assert Lead.objects.count() == 0


# ── Admin management ────────────────────────────────────────────────────────
def test_admin_lists_leads(super_admin):
    Lead.objects.create(**VALID)
    res = _admin(super_admin).get(ADMIN)
    assert res.status_code == 200
    assert len(res.data) == 1
    assert res.data[0]["email"] == "ali@bloomcafe.com"


def test_admin_requires_auth():
    Lead.objects.create(**VALID)
    assert APIClient().get(ADMIN).status_code in (401, 403)


def test_mark_contacted_sets_timestamp_and_audits(super_admin):
    lead = Lead.objects.create(**VALID)
    res = _admin(super_admin).patch(f"{ADMIN}/{lead.id}", {"status": "contacted"}, format="json")
    assert res.status_code == 200
    lead.refresh_from_db()
    assert lead.status == Lead.Status.CONTACTED
    assert lead.contacted_at is not None
    assert AdminAuditLog.objects.filter(action="lead.update").exists()


def test_delete_lead(super_admin):
    lead = Lead.objects.create(**VALID)
    res = _admin(super_admin).delete(f"{ADMIN}/{lead.id}")
    assert res.status_code == 204
    assert Lead.objects.count() == 0
    assert AdminAuditLog.objects.filter(action="lead.delete").exists()
