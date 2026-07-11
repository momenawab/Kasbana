"""Merchant support tests (finalize Phase B).

A logged-in merchant opens a support message from the dashboard; it becomes a
`console.ContactMessage` with `source=dashboard` + `merchant` set, surfaces on
that merchant's admin Support tab, and the team replies with the branded email
flow. Covers identity-from-session (no spoofing), tenancy, the admin per-merchant
list + its auth gate, the reply lifecycle, and that the marketing intake still
defaults to `source=marketing` with a null merchant.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminUser, ContactMessage
from core.enums import Role
from tests import factories

pytestmark = pytest.mark.django_db

DASH = "/api/v1/support/messages"


def _merchant_client(staff):
    from rest_framework_simplejwt.tokens import RefreshToken

    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(staff.user).access_token}")
    return c


@pytest.fixture
def owner(merchant):
    return factories.StaffUserFactory(
        merchant=merchant,
        role=Role.OWNER,
        user=factories.UserFactory(email="owner@shop.com", first_name="Sara", last_name="Nabil"),
    )


@pytest.fixture
def support_admin():
    a = AdminUser(email="support@stampn.net", name="Support", role=AdminRole.SUPPORT)
    a.set_password("supersecret1")
    a.save()
    return a


def _admin(admin):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return c


# ── merchant dashboard endpoint ───────────────────────────────────────────────


def test_merchant_can_open_a_support_message(owner, merchant):
    res = _merchant_client(owner).post(
        DASH, {"subject": "Wallet not updating", "message": "Stamps don't sync."}, format="json"
    )
    assert res.status_code == 201
    msg = ContactMessage.objects.get()
    assert msg.merchant_id == merchant.id
    assert msg.source == ContactMessage.Source.DASHBOARD
    assert msg.status == ContactMessage.Status.NEW
    # Identity is pulled from the session, not the body.
    assert msg.email == "owner@shop.com"
    assert msg.name == "Sara Nabil"


def test_sender_identity_cannot_be_spoofed_via_body(owner, merchant):
    """A merchant must not be able to submit under another person's name/email."""
    _merchant_client(owner).post(
        DASH,
        {
            "subject": "Hi",
            "message": "spoof attempt",
            "email": "victim@elsewhere.com",
            "name": "Someone Else",
            "merchant": "11111111-1111-1111-1111-111111111111",
        },
        format="json",
    )
    msg = ContactMessage.objects.get()
    assert msg.email == "owner@shop.com"
    assert msg.name == "Sara Nabil"
    assert msg.merchant_id == merchant.id


def test_name_falls_back_to_business_when_user_has_no_name(merchant):
    staff = factories.StaffUserFactory(
        merchant=merchant,
        role=Role.OWNER,
        user=factories.UserFactory(email="noname@shop.com", first_name="", last_name=""),
    )
    _merchant_client(staff).post(DASH, {"subject": "x", "message": "y"}, format="json")
    assert ContactMessage.objects.get().name == merchant.name


def test_missing_content_rejected(owner):
    assert _merchant_client(owner).post(DASH, {"subject": "only"}, format="json").status_code == 400
    assert _merchant_client(owner).post(DASH, {"message": "only"}, format="json").status_code == 400
    assert ContactMessage.objects.count() == 0


def test_merchant_lists_only_its_own_messages(owner, merchant):
    factories_other = factories.StaffUserFactory(role=Role.OWNER)
    ContactMessage.objects.create(
        merchant=merchant,
        source=ContactMessage.Source.DASHBOARD,
        name="a",
        email="a@a.com",
        subject="mine",
        message="m",
    )
    ContactMessage.objects.create(
        merchant=factories_other.merchant,
        source=ContactMessage.Source.DASHBOARD,
        name="b",
        email="b@b.com",
        subject="theirs",
        message="m",
    )
    # A marketing message (no merchant) must never leak into a merchant's list.
    ContactMessage.objects.create(name="c", email="c@c.com", subject="public", message="m")

    res = _merchant_client(owner).get(DASH)
    assert res.status_code == 200
    subjects = {r["subject"] for r in res.data}
    assert subjects == {"mine"}


def test_dashboard_support_requires_auth(api_client):
    assert api_client.get(DASH).status_code == 401
    assert api_client.post(DASH, {"subject": "x", "message": "y"}, format="json").status_code == 401


# ── admin per-merchant list + reply ───────────────────────────────────────────


def test_admin_lists_a_merchants_dashboard_messages(support_admin, merchant):
    ContactMessage.objects.create(
        merchant=merchant,
        source=ContactMessage.Source.DASHBOARD,
        name="Sara",
        email="owner@shop.com",
        subject="Help",
        message="please",
    )
    # Another merchant's message must not show here.
    ContactMessage.objects.create(
        merchant=factories.MerchantFactory(),
        source=ContactMessage.Source.DASHBOARD,
        name="Other",
        email="o@o.com",
        subject="Nope",
        message="x",
    )
    url = f"/api/admin/v1/merchants/{merchant.id}/support/messages"
    res = _admin(support_admin).get(url)
    assert res.status_code == 200
    assert [r["subject"] for r in res.data] == ["Help"]
    assert res.data[0]["source"] == "dashboard"
    assert res.data[0]["merchant_name"] == merchant.name


def test_admin_per_merchant_list_requires_admin_auth(api_client, owner, merchant):
    """A merchant's own JWT must not reach the admin console list."""
    url = f"/api/admin/v1/merchants/{merchant.id}/support/messages"
    assert _merchant_client(owner).get(url).status_code in (401, 403)


def test_admin_reply_marks_replied_and_emails(support_admin, merchant, settings, mailoutbox):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    msg = ContactMessage.objects.create(
        merchant=merchant,
        source=ContactMessage.Source.DASHBOARD,
        name="Sara",
        email="owner@shop.com",
        subject="Help",
        message="please",
    )
    res = _admin(support_admin).post(
        f"/api/admin/v1/messages/{msg.id}/reply", {"message": "On it!"}, format="json"
    )
    assert res.status_code == 200
    msg.refresh_from_db()
    assert msg.status == ContactMessage.Status.REPLIED
    assert msg.replied_at is not None
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["owner@shop.com"]


# ── existing marketing intake is untouched ────────────────────────────────────


def test_marketing_intake_still_defaults_to_marketing_source(api_client):
    api_client.post(
        "/api/v1/contact",
        {"name": "Ali", "email": "ali@x.com", "subject": "Q", "message": "hi"},
        format="json",
    )
    msg = ContactMessage.objects.get()
    assert msg.source == ContactMessage.Source.MARKETING
    assert msg.merchant is None
