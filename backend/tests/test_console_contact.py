"""Inbound support/contact message tests.

Covers the public (unauthenticated) intake from the marketing site — including
validation and the bot honeypot — plus the admin console list / mark-read /
delete flow and its audit trail.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser, ContactMessage

pytestmark = pytest.mark.django_db

PUBLIC = "/api/v1/contact"
ADMIN = "/api/admin/v1/messages"

VALID = {
    "name": "Ali Hassan",
    "email": "ali@bloomcafe.com",
    "subject": "Pricing question",
    "message": "How much is the Growth plan?",
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
def test_public_can_create_message_without_auth():
    res = APIClient().post(PUBLIC, VALID, format="json")
    assert res.status_code == 201
    msg = ContactMessage.objects.get()
    assert msg.subject == "Pricing question"
    assert msg.status == ContactMessage.Status.NEW


def test_missing_fields_rejected():
    res = APIClient().post(PUBLIC, {"name": "Ali"}, format="json")
    assert res.status_code == 400
    assert ContactMessage.objects.count() == 0


def test_honeypot_is_accepted_but_saves_nothing():
    res = APIClient().post(PUBLIC, {**VALID, "botcheck": "spam"}, format="json")
    assert res.status_code == 201
    assert ContactMessage.objects.count() == 0


# ── Admin management ────────────────────────────────────────────────────────
def test_admin_lists_messages(super_admin):
    ContactMessage.objects.create(**VALID)
    res = _admin(super_admin).get(ADMIN)
    assert res.status_code == 200
    assert len(res.data) == 1
    assert res.data[0]["email"] == "ali@bloomcafe.com"


def test_admin_requires_auth():
    ContactMessage.objects.create(**VALID)
    assert APIClient().get(ADMIN).status_code in (401, 403)


def test_mark_read_sets_timestamp_and_audits(super_admin):
    msg = ContactMessage.objects.create(**VALID)
    res = _admin(super_admin).patch(f"{ADMIN}/{msg.id}", {"status": "read"}, format="json")
    assert res.status_code == 200
    msg.refresh_from_db()
    assert msg.status == ContactMessage.Status.READ
    assert msg.read_at is not None
    assert AdminAuditLog.objects.filter(action="contact_message.update").exists()


def test_delete_message(super_admin):
    msg = ContactMessage.objects.create(**VALID)
    res = _admin(super_admin).delete(f"{ADMIN}/{msg.id}")
    assert res.status_code == 204
    assert ContactMessage.objects.count() == 0
    assert AdminAuditLog.objects.filter(action="contact_message.delete").exists()
