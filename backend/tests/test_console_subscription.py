"""Admin subscription management tests (Phase 4).

Covers the role gate (reads open to any admin, mutations Finance/Super-admin
only), the direct plan/status PATCH incl. the downgrade guardrail, extend-trial,
comp (bypasses a lock), lock/unlock, the audit trail, and that ``override_plan``
takes precedence over everything — including a lock — in live entitlements.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from billing import entitlements, services
from billing.models import Subscription
from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser
from core.enums import PlanTier
from tests import factories

pytestmark = pytest.mark.django_db


def _sub_url(merchant, suffix=""):
    return f"/api/admin/v1/merchants/{merchant.id}/subscription{suffix}"


@pytest.fixture
def super_admin():
    admin = AdminUser(email="super@stampn.net", name="Super", role=AdminRole.SUPER_ADMIN)
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
def support_admin():
    admin = AdminUser(email="support@stampn.net", name="Support", role=AdminRole.SUPPORT)
    admin.set_password("supersecret1")
    admin.save()
    return admin


def _bearer(client, admin):
    access = issue_admin_tokens(admin)["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


# ── reads ─────────────────────────────────────────────────────────────────────
def test_any_admin_can_read_subscription(api_client, support_admin, merchant):
    resp = _bearer(api_client, support_admin).get(_sub_url(merchant))
    assert resp.status_code == 200
    assert resp.json()["status"] == "TRIALING"
    assert resp.json()["effective_plan"] == PlanTier.GROWTH


def test_unauthenticated_request_rejected(api_client, merchant):
    assert api_client.get(_sub_url(merchant)).status_code == 401


# ── role gate on mutations ─────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("patch", "", {"plan": "STARTER", "reason": "x"}),
        ("post", "/extend-trial", {"days": 7}),
        ("post", "/comp", {"on": True, "reason": "x"}),
        ("post", "/lock", {"reason": "x"}),
        ("post", "/unlock", {"reason": "x"}),
    ],
)
def test_support_admin_cannot_mutate_subscription(
    api_client, support_admin, merchant, method, suffix, body
):
    client = _bearer(api_client, support_admin)
    resp = getattr(client, method)(_sub_url(merchant, suffix), body, format="json")
    assert resp.status_code == 403


# ── PATCH: plan/status/override/notes ───────────────────────────────────────────
def test_finance_admin_can_change_plan(api_client, finance_admin, merchant):
    resp = _bearer(api_client, finance_admin).patch(
        _sub_url(merchant), {"plan": "STARTER", "reason": "manual upgrade"}, format="json"
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["plan"] == "STARTER"
    assert resp.json()["status"] == "ACTIVE"
    merchant.refresh_from_db()
    assert merchant.plan == "STARTER"
    log = AdminAuditLog.objects.get(action="subscription.update", target_id=str(merchant.id))
    assert log.metadata["reason"] == "manual upgrade"


def test_patch_requires_reason(api_client, finance_admin, merchant):
    resp = _bearer(api_client, finance_admin).patch(
        _sub_url(merchant), {"plan": "STARTER"}, format="json"
    )
    assert resp.status_code == 400


def test_downgrade_blocked_when_usage_exceeds_new_plan(api_client, super_admin, merchant):
    services.activate_plan(merchant, PlanTier.GROWTH)
    for _ in range(5):
        factories.CardFactory(merchant=merchant)  # STARTER's max_cards is 3

    resp = _bearer(api_client, super_admin).patch(
        _sub_url(merchant), {"plan": "STARTER", "reason": "downgrade"}, format="json"
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PLAN_DOWNGRADE_BLOCKED"
    assert "max_cards" in resp.json()["error"]["shortfall"]
    merchant.refresh_from_db()
    assert merchant.plan == PlanTier.GROWTH  # unchanged


def test_downgrade_forced_through_despite_shortfall(api_client, super_admin, merchant):
    services.activate_plan(merchant, PlanTier.GROWTH)
    for _ in range(5):
        factories.CardFactory(merchant=merchant)

    resp = _bearer(api_client, super_admin).patch(
        _sub_url(merchant),
        {"plan": "STARTER", "reason": "forced downgrade", "force": True},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["plan"] == "STARTER"


def test_patch_sets_explicit_status_over_activate_plan_default(api_client, super_admin, merchant):
    resp = _bearer(api_client, super_admin).patch(
        _sub_url(merchant),
        {"plan": "STARTER", "status": "PAST_DUE", "reason": "test"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PAST_DUE"  # not ACTIVE, despite activate_plan's default


def test_patch_status_only_locks_without_touching_plan(api_client, super_admin, merchant):
    resp = _bearer(api_client, super_admin).patch(
        _sub_url(merchant), {"status": "LOCKED", "reason": "manual lock"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "LOCKED"
    assert entitlements.check(merchant, "max_cards") is False


# ── extend-trial ─────────────────────────────────────────────────────────────
def test_extend_trial_resets_status_and_pushes_end_date(api_client, super_admin, merchant):
    services.lock(merchant)
    resp = _bearer(api_client, super_admin).post(
        _sub_url(merchant, "/extend-trial"), {"days": 10}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "TRIALING"
    sub = Subscription.objects.get(merchant=merchant)
    assert sub.trial_ends_at > timezone.now() + timedelta(days=9)
    assert AdminAuditLog.objects.filter(
        action="subscription.extend_trial", target_id=str(merchant.id)
    ).exists()


def test_extend_trial_reason_optional(api_client, super_admin, merchant):
    resp = _bearer(api_client, super_admin).post(
        _sub_url(merchant, "/extend-trial"), {"days": 5}, format="json"
    )
    assert resp.status_code == 200


# ── comp ─────────────────────────────────────────────────────────────────────
def test_comp_grants_access_despite_lock(api_client, super_admin, merchant):
    services.activate_plan(merchant, PlanTier.STARTER)
    services.lock(merchant)
    assert entitlements.check(merchant, "export") is False

    resp = _bearer(api_client, super_admin).post(
        _sub_url(merchant, "/comp"), {"on": True, "reason": "goodwill"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["comp"] is True
    assert entitlements.check(merchant, "export") is True  # Starter has export


def test_comp_requires_reason(api_client, super_admin, merchant):
    resp = _bearer(api_client, super_admin).post(
        _sub_url(merchant, "/comp"), {"on": True}, format="json"
    )
    assert resp.status_code == 400


# ── lock / unlock ────────────────────────────────────────────────────────────
def test_lock_then_unlock_round_trip(api_client, super_admin, merchant):
    services.activate_plan(merchant, PlanTier.STARTER)

    lock_resp = _bearer(api_client, super_admin).post(
        _sub_url(merchant, "/lock"), {"reason": "chargeback"}, format="json"
    )
    assert lock_resp.status_code == 200
    assert lock_resp.json()["status"] == "LOCKED"
    assert entitlements.check(merchant, "max_cards") is False

    unlock_resp = _bearer(api_client, super_admin).post(
        _sub_url(merchant, "/unlock"), {"reason": "resolved"}, format="json"
    )
    assert unlock_resp.status_code == 200
    assert unlock_resp.json()["status"] == "ACTIVE"
    assert entitlements.check(merchant, "max_cards") is True


# ── override precedence ────────────────────────────────────────────────────────
def test_override_plan_wins_over_a_lock(api_client, super_admin, merchant):
    services.lock(merchant)
    resp = _bearer(api_client, super_admin).patch(
        _sub_url(merchant),
        {"override_plan": "CHAIN", "reason": "emergency unblock"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["effective_plan"] == "CHAIN"
    assert entitlements.check(merchant, "max_cards") is True  # CHAIN = unlimited


def test_expired_override_falls_back_to_normal_resolution(api_client, super_admin, merchant):
    services.lock(merchant)
    resp = _bearer(api_client, super_admin).patch(
        _sub_url(merchant),
        {
            "override_plan": "CHAIN",
            "override_expires_at": (timezone.now() - timedelta(days=1)).isoformat(),
            "reason": "already expired",
        },
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["effective_plan"] is None  # override expired, still locked


# ── audit trail ────────────────────────────────────────────────────────────────
def test_audit_trail_lists_subscription_actions(api_client, super_admin, merchant):
    _bearer(api_client, super_admin).post(
        _sub_url(merchant, "/lock"), {"reason": "test"}, format="json"
    )
    _bearer(api_client, super_admin).post(
        _sub_url(merchant, "/unlock"), {"reason": "test"}, format="json"
    )
    resp = _bearer(api_client, super_admin).get(_sub_url(merchant, "/audit"))
    assert resp.status_code == 200
    actions = [row["action"] for row in resp.json()]
    assert actions == ["subscription.unlock", "subscription.lock"]  # newest first


def test_audit_trail_open_to_any_admin(api_client, support_admin, merchant):
    resp = _bearer(api_client, support_admin).get(_sub_url(merchant, "/audit"))
    assert resp.status_code == 200
