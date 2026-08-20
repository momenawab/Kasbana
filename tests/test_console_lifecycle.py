"""Merchant lifecycle & moderation tests (Phase 9).

Covers the lifecycle pipeline staging, at-risk health scoring + reasons, the
Super-admin suspend/unsuspend gate AND its enforcement on the merchant API (a
suspended merchant is immediately blocked but can still load /me), and the
moderation queue — heuristic scan (idempotent), Support+ resolve gate, and
approve/reject.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from billing.models import Invoice, InvoiceStatus
from billing.plans import BillingStatus
from billing.services import subscription_for
from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser, ContentFlag
from core.enums import LedgerEvent, MerchantStatus
from core.models import StampLedger
from tests import factories

pytestmark = pytest.mark.django_db


@pytest.fixture
def super_admin():
    a = AdminUser(email="super@stampn.net", role=AdminRole.SUPER_ADMIN)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def support_admin():
    a = AdminUser(email="support@stampn.net", role=AdminRole.SUPPORT)
    a.set_password("supersecret1")
    a.save()
    return a


def _bearer(_client, admin):
    # A FRESH client — the shared `api_client`/`auth_client` are the same instance,
    # so reusing it would clobber the merchant token in the enforcement tests.
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return c


def _recent_stamp(merchant):
    card = factories.CardFactory(merchant=merchant)
    cc = factories.CustomerCardFactory(card=card, merchant=merchant)
    StampLedger.objects.create(
        customer_card=cc, merchant=merchant, event_type=LedgerEvent.STAMP, delta=1, balance_after=1
    )


# ── lifecycle pipeline ─────────────────────────────────────────────────────────
def test_pipeline_stages(api_client, support_admin):
    lead = factories.MerchantFactory()  # no subscription row

    trial = factories.MerchantFactory()
    subscription_for(trial)  # default active trial

    active = factories.MerchantFactory()
    a = subscription_for(active)
    a.status = BillingStatus.ACTIVE
    a.save()

    churned = factories.MerchantFactory()
    c = subscription_for(churned)
    c.status = BillingStatus.LOCKED
    c.save()

    data = _bearer(api_client, support_admin).get("/api/admin/v1/lifecycle/pipeline").json()
    counts = {s["stage"]: s["count"] for s in data["stages"]}
    assert counts == {"lead": 1, "trial": 1, "active": 1, "churned": 1}
    ids = {s["stage"]: [m["id"] for m in s["merchants"]] for s in data["stages"]}
    assert str(lead.id) in ids["lead"]
    assert str(churned.id) in ids["churned"]


def test_expired_trial_is_churned(api_client, support_admin):
    m = factories.MerchantFactory()
    sub = subscription_for(m)
    sub.status = BillingStatus.TRIALING
    sub.trial_ends_at = timezone.now() - timedelta(days=1)  # expired
    sub.save()

    data = _bearer(api_client, support_admin).get("/api/admin/v1/lifecycle/pipeline").json()
    counts = {s["stage"]: s["count"] for s in data["stages"]}
    assert counts["churned"] == 1
    assert counts["trial"] == 0


# ── at-risk / health ───────────────────────────────────────────────────────────
def test_at_risk_flags_trial_ending_and_low_activity(api_client, support_admin):
    m = factories.MerchantFactory(name="Risky")
    sub = subscription_for(m)
    sub.status = BillingStatus.TRIALING
    sub.trial_ends_at = timezone.now() + timedelta(days=2)  # ending soon
    sub.save()

    rows = _bearer(api_client, support_admin).get("/api/admin/v1/lifecycle/at-risk").json()
    risky = next(r for r in rows if r["id"] == str(m.id))
    assert risky["health_score"] < 70
    assert "trial ending" in risky["reasons"]
    assert "low activity" in risky["reasons"]


def test_failed_payment_is_a_risk_signal(api_client, support_admin):
    m = factories.MerchantFactory()
    sub = subscription_for(m)
    sub.status = BillingStatus.ACTIVE
    sub.save()
    _recent_stamp(m)  # healthy activity
    Invoice.objects.create(
        merchant=m, amount_egp=299, status=InvoiceStatus.FAILED, provider="paymob"
    )

    rows = _bearer(api_client, support_admin).get("/api/admin/v1/lifecycle/at-risk").json()
    risky = next(r for r in rows if r["id"] == str(m.id))
    assert "failed payment" in risky["reasons"]


def test_healthy_active_merchant_not_at_risk(api_client, support_admin):
    m = factories.MerchantFactory(name="Healthy")
    sub = subscription_for(m)
    sub.status = BillingStatus.ACTIVE
    sub.save()
    _recent_stamp(m)
    Invoice.objects.create(merchant=m, amount_egp=299, status=InvoiceStatus.PAID, provider="paymob")

    rows = _bearer(api_client, support_admin).get("/api/admin/v1/lifecycle/at-risk").json()
    assert all(r["id"] != str(m.id) for r in rows)


# ── suspend / unsuspend + enforcement ──────────────────────────────────────────
def test_suspend_requires_super_admin(api_client, support_admin, merchant):
    resp = _bearer(api_client, support_admin).post(
        f"/api/admin/v1/merchants/{merchant.id}/suspend", {"reason": "spam"}, format="json"
    )
    assert resp.status_code == 403


def test_suspend_sets_status_and_audits(api_client, super_admin, merchant):
    resp = _bearer(api_client, super_admin).post(
        f"/api/admin/v1/merchants/{merchant.id}/suspend", {"reason": "abuse"}, format="json"
    )
    assert resp.status_code == 200
    merchant.refresh_from_db()
    assert merchant.status == MerchantStatus.SUSPENDED
    assert AdminAuditLog.objects.filter(action="merchant.suspend").exists()


def test_suspended_merchant_is_blocked_on_merchant_api(
    auth_client, api_client, super_admin, merchant
):
    # Baseline: the merchant's staff can use the API.
    assert auth_client.get("/api/v1/settings/account").status_code == 200

    _bearer(api_client, super_admin).post(
        f"/api/admin/v1/merchants/{merchant.id}/suspend", {"reason": "abuse"}, format="json"
    )

    # Now blocked everywhere...
    assert auth_client.get("/api/v1/settings/account").status_code == 403
    # ...but /me still resolves so the dashboard can show the suspended state.
    me = auth_client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["merchant"]["status"] == "suspended"


def test_unsuspend_restores_access(auth_client, api_client, super_admin, merchant):
    _bearer(api_client, super_admin).post(
        f"/api/admin/v1/merchants/{merchant.id}/suspend", {"reason": "x"}, format="json"
    )
    assert auth_client.get("/api/v1/settings/account").status_code == 403

    resp = _bearer(api_client, super_admin).post(
        f"/api/admin/v1/merchants/{merchant.id}/unsuspend", {"reason": "resolved"}, format="json"
    )
    assert resp.status_code == 200
    assert auth_client.get("/api/v1/settings/account").status_code == 200
    assert AdminAuditLog.objects.filter(action="merchant.unsuspend").exists()


# ── moderation ──────────────────────────────────────────────────────────────────
def test_scan_flags_banned_keyword_and_is_idempotent(api_client, support_admin, merchant):
    factories.CardFactory(merchant=merchant, name="Casino Rewards Club")

    r1 = _bearer(api_client, support_admin).post("/api/admin/v1/moderation/scan").json()
    assert r1["created"] == 1
    # Re-running must not duplicate the pending flag.
    r2 = _bearer(api_client, support_admin).post("/api/admin/v1/moderation/scan").json()
    assert r2["created"] == 0
    assert ContentFlag.objects.filter(status=ContentFlag.Status.PENDING).count() == 1


def test_scan_requires_support(api_client, merchant):
    ro = AdminUser(email="ro@stampn.net", role=AdminRole.READ_ONLY)
    ro.set_password("supersecret1")
    ro.save()
    assert _bearer(api_client, ro).post("/api/admin/v1/moderation/scan").status_code == 403


def test_queue_and_resolve_reject(api_client, support_admin, merchant):
    factories.CardFactory(merchant=merchant, name="XXX Deals")
    _bearer(api_client, support_admin).post("/api/admin/v1/moderation/scan")

    queue = _bearer(api_client, support_admin).get("/api/admin/v1/moderation/flags").json()
    assert len(queue) == 1
    flag_id = queue[0]["id"]

    resolved = (
        _bearer(api_client, support_admin)
        .post(
            f"/api/admin/v1/moderation/flags/{flag_id}/resolve",
            {"action": "reject", "notes": "clear violation"},
            format="json",
        )
        .json()
    )
    assert resolved["status"] == "rejected"
    assert AdminAuditLog.objects.filter(action="moderation.resolve").exists()
    # No longer in the pending queue.
    assert _bearer(api_client, support_admin).get("/api/admin/v1/moderation/flags").json() == []


def test_resolve_already_resolved_is_409(api_client, support_admin, merchant):
    flag = ContentFlag.objects.create(
        merchant=merchant,
        target_type=ContentFlag.TargetType.MERCHANT,
        target_id=str(merchant.id),
        reason="banned keyword: scam",
        status=ContentFlag.Status.APPROVED,
    )
    resp = _bearer(api_client, support_admin).post(
        f"/api/admin/v1/moderation/flags/{flag.id}/resolve", {"action": "reject"}, format="json"
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "FLAG_ALREADY_RESOLVED"


def test_merchant_token_cannot_reach_lifecycle(api_client, merchant):
    staff = factories.StaffUserFactory(merchant=merchant)
    token = str(RefreshToken.for_user(staff.user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert api_client.get("/api/admin/v1/lifecycle/pipeline").status_code in (401, 403)
