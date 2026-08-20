"""Support tools & impersonation tests (Phase 6).

Covers the auth boundary (merchant tokens rejected by the admin endpoints),
the Support/Super-admin role gate (Finance deliberately excluded), the full
impersonation lifecycle — mint → use on the merchant API → tagged mutations →
billing blocked → admin end kills the token → expiry kills the token — plus
the support actions, the notes thread, and the cross-sourced activity timeline.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import PasswordResetToken, StaffInvite
from billing.models import InvoiceStatus
from billing.services import record_invoice, subscription_for
from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser, Impersonation, SupportNote
from core.enums import Role
from tests import factories

pytestmark = pytest.mark.django_db

BASE = "/api/admin/v1/merchants"


@pytest.fixture
def super_admin():
    admin = AdminUser(email="super@stampn.net", name="Super", role=AdminRole.SUPER_ADMIN)
    admin.set_password("supersecret1")
    admin.save()
    return admin


@pytest.fixture
def support_admin():
    admin = AdminUser(email="support@stampn.net", name="Support", role=AdminRole.SUPPORT)
    admin.set_password("supersecret1")
    admin.save()
    return admin


@pytest.fixture
def finance_admin():
    admin = AdminUser(email="finance@stampn.net", name="Finance", role=AdminRole.FINANCE)
    admin.set_password("supersecret1")
    admin.save()
    return admin


@pytest.fixture
def owner(merchant):
    return factories.StaffUserFactory(merchant=merchant, role=Role.OWNER)


def _bearer(client, admin):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return client


def _impersonate(client, admin, merchant, reason="ticket #42"):
    return _bearer(client, admin).post(
        f"{BASE}/{merchant.id}/impersonate", {"reason": reason}, format="json"
    )


# ── boundary + role gate ──────────────────────────────────────────────────────
def test_unauthenticated_rejected(api_client, merchant):
    assert api_client.get(f"{BASE}/{merchant.id}/activity").status_code == 401
    assert api_client.post(f"{BASE}/{merchant.id}/impersonate").status_code == 401


def test_merchant_token_cannot_reach_support_endpoints(api_client, owner, merchant):
    token = str(RefreshToken.for_user(owner.user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert api_client.get(f"{BASE}/{merchant.id}/support/notes").status_code in (401, 403)
    assert api_client.post(f"{BASE}/{merchant.id}/impersonate").status_code in (401, 403)


@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("post", "/impersonate", {"reason": "x"}),
        ("post", "/support/send-password-reset", {}),
        ("post", "/support/resend-invite", {"email": "a@b.c"}),
        ("post", "/support/clear-stuck-checkout", {"reason": "x"}),
        ("post", "/support/notes", {"body": "x"}),
    ],
)
def test_finance_admin_cannot_use_support_tools(
    api_client, finance_admin, merchant, method, suffix, body
):
    resp = getattr(_bearer(api_client, finance_admin), method)(
        f"{BASE}/{merchant.id}{suffix}", body, format="json"
    )
    assert resp.status_code == 403


def test_any_admin_can_read_notes_and_activity(api_client, finance_admin, merchant):
    client = _bearer(api_client, finance_admin)
    assert client.get(f"{BASE}/{merchant.id}/support/notes").status_code == 200
    assert client.get(f"{BASE}/{merchant.id}/activity").status_code == 200
    assert client.get(f"{BASE}/{merchant.id}/impersonations").status_code == 200


# ── impersonation lifecycle ───────────────────────────────────────────────────
def test_impersonate_mints_a_working_merchant_session(api_client, support_admin, owner, merchant):
    resp = _impersonate(api_client, support_admin, merchant)
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_email"] == owner.user.email

    imp = Impersonation.objects.get(id=body["impersonation_id"])
    assert imp.is_active() and imp.admin_email == support_admin.email

    log = AdminAuditLog.objects.filter(action="impersonation.start").first()
    assert log is not None and log.target_id == str(merchant.id)

    # The token works on the merchant API, scoped to THIS merchant, and /me
    # flags the impersonation so the dashboard can show its banner.
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")
    me = api_client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["merchant"]["id"] == str(merchant.id)
    assert me.json()["impersonation"]["admin_email"] == support_admin.email


def test_impersonate_prefers_owner_over_other_staff(api_client, support_admin, merchant):
    factories.StaffUserFactory(merchant=merchant, role=Role.ADMIN)
    owner = factories.StaffUserFactory(merchant=merchant, role=Role.OWNER)
    resp = _impersonate(api_client, support_admin, merchant)
    assert resp.json()["target_email"] == owner.user.email


def test_impersonate_without_staff_is_409(api_client, support_admin, merchant):
    resp = _impersonate(api_client, support_admin, merchant)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "NO_ACTIVE_STAFF"


def test_impersonated_token_cannot_touch_billing(api_client, support_admin, owner, merchant):
    body = _impersonate(api_client, support_admin, merchant).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")
    assert api_client.get("/api/v1/billing").status_code == 403
    assert api_client.post("/api/v1/billing/subscribe", {"plan": "growth"}).status_code == 403


def test_impersonated_mutation_is_tagged_in_admin_audit(api_client, support_admin, owner, merchant):
    body = _impersonate(api_client, support_admin, merchant).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")
    api_client.patch("/api/v1/settings/account", {"language": "en"}, format="json")

    log = AdminAuditLog.objects.filter(action="impersonation.request").first()
    assert log is not None
    assert log.actor_email == support_admin.email
    assert log.target_id == str(merchant.id)
    assert log.metadata["method"] == "PATCH"


def test_admin_end_kills_the_token_before_jwt_expiry(api_client, support_admin, owner, merchant):
    body = _impersonate(api_client, support_admin, merchant).json()

    end = _bearer(api_client, support_admin).post(
        "/api/admin/v1/impersonate/end",
        {"impersonation_id": body["impersonation_id"]},
        format="json",
    )
    assert end.status_code == 200 and end.json()["active"] is False

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")
    assert api_client.get("/api/v1/me").status_code == 401
    assert AdminAuditLog.objects.filter(action="impersonation.end").exists()


def test_expired_impersonation_is_rejected(api_client, support_admin, owner, merchant):
    body = _impersonate(api_client, support_admin, merchant).json()
    Impersonation.objects.filter(id=body["impersonation_id"]).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")
    assert api_client.get("/api/v1/me").status_code == 401


def test_normal_merchant_token_is_unaffected(auth_client):
    me = auth_client.get("/api/v1/me")
    assert me.status_code == 200
    assert "impersonation" not in me.json()


# ── support actions ───────────────────────────────────────────────────────────
def test_send_password_reset_creates_token_and_audits(
    api_client, support_admin, owner, merchant, mailoutbox
):
    resp = _bearer(api_client, support_admin).post(
        f"{BASE}/{merchant.id}/support/send-password-reset"
    )
    assert resp.status_code == 200 and resp.json()["ok"] is True
    assert PasswordResetToken.objects.filter(user=owner.user).exists()
    assert len(mailoutbox) == 1 and owner.user.email in mailoutbox[0].to
    assert AdminAuditLog.objects.filter(action="support.send_password_reset").exists()


def test_send_password_reset_without_staff_is_409(api_client, support_admin, merchant):
    resp = _bearer(api_client, support_admin).post(
        f"{BASE}/{merchant.id}/support/send-password-reset"
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "NO_OWNER_EMAIL"


def test_resend_invite_extends_expiry_and_emails(api_client, support_admin, merchant, mailoutbox):
    invite = StaffInvite.objects.create(
        merchant=merchant,
        email="newstaff@shop.com",
        role=Role.SCANNER,
        expires_at=timezone.now() + timedelta(hours=1),
    )
    resp = _bearer(api_client, support_admin).post(
        f"{BASE}/{merchant.id}/support/resend-invite", {"email": "newstaff@shop.com"}
    )
    assert resp.status_code == 200
    invite.refresh_from_db()
    assert invite.expires_at > timezone.now() + timedelta(days=6)
    assert len(mailoutbox) == 1 and invite.token in mailoutbox[0].body
    assert AdminAuditLog.objects.filter(action="support.resend_invite").exists()


def test_resend_invite_unknown_email_is_404(api_client, support_admin, merchant):
    resp = _bearer(api_client, support_admin).post(
        f"{BASE}/{merchant.id}/support/resend-invite", {"email": "ghost@shop.com"}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "INVITE_NOT_FOUND"


def test_clear_stuck_checkout(api_client, support_admin, merchant):
    sub = subscription_for(merchant)
    sub.pending_plan = "GROWTH"
    sub.save(update_fields=["pending_plan"])

    resp = _bearer(api_client, support_admin).post(
        f"{BASE}/{merchant.id}/support/clear-stuck-checkout", {"reason": "abandoned checkout"}
    )
    assert resp.status_code == 200
    sub.refresh_from_db()
    assert sub.pending_plan == ""
    log = AdminAuditLog.objects.filter(action="support.clear_stuck_checkout").first()
    assert log is not None and log.metadata["before"]["pending_plan"] == "GROWTH"


def test_clear_stuck_checkout_without_pending_is_409(api_client, support_admin, merchant):
    resp = _bearer(api_client, support_admin).post(
        f"{BASE}/{merchant.id}/support/clear-stuck-checkout", {"reason": "x"}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "NO_PENDING_CHECKOUT"


# ── notes + timeline ──────────────────────────────────────────────────────────
def test_notes_thread_roundtrip(api_client, support_admin, merchant):
    client = _bearer(api_client, support_admin)
    created = client.post(
        f"{BASE}/{merchant.id}/support/notes", {"body": "Called the owner, resolved."}
    )
    assert created.status_code == 201
    assert created.json()["admin_email"] == support_admin.email

    listed = client.get(f"{BASE}/{merchant.id}/support/notes").json()
    assert len(listed) == 1 and listed[0]["body"] == "Called the owner, resolved."
    assert SupportNote.objects.filter(merchant=merchant).count() == 1
    assert AdminAuditLog.objects.filter(action="support.note").exists()


def test_activity_timeline_cross_sources_events(api_client, support_admin, merchant, card):
    from core.enums import LedgerEvent
    from core.models import StampLedger

    cc = factories.CustomerCardFactory(card=card, merchant=merchant)
    StampLedger.objects.create(
        customer_card=cc,
        merchant=merchant,
        event_type=LedgerEvent.STAMP,
        delta=1,
        balance_after=1,
    )
    record_invoice(merchant, amount_egp=Decimal("299"), status=InvoiceStatus.PAID)
    AdminAuditLog.objects.create(
        actor_email="ops@stampn.net",
        action="subscription.lock",
        target_type="subscription",
        target_id=str(merchant.id),
        metadata={"reason": "test"},
    )

    events = _bearer(api_client, support_admin).get(f"{BASE}/{merchant.id}/activity").json()
    types = {e["type"] for e in events}
    assert "invoice_paid" in types
    assert "admin_action" in types
    assert types & {"stamp", "enroll", "redeem", "adjust"}  # from the ledger factory
    ats = [e["at"] for e in events]
    assert ats == sorted(ats, reverse=True)
