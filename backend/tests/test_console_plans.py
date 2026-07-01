"""Admin plan catalogue tests (Phase 3).

Covers the auth/role boundary (any admin reads, only Finance/Super-admin
mutates), the CRUD happy path, audit-write, and that edits actually flow
through to the entitlements engine (``plan_limits_map``/``check``).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from billing import entitlements, services
from billing.models import Plan
from billing.plans import invalidate_plan_cache, plan_price
from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser
from core.enums import PlanTier
from tests import factories

pytestmark = pytest.mark.django_db

PLANS = "/api/admin/v1/plans"


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


# ── seed + read ───────────────────────────────────────────────────────────────
def test_seed_migration_created_the_four_plans():
    assert set(Plan.objects.values_list("key", flat=True)) == {
        "FREE",
        "STARTER",
        "GROWTH",
        "CHAIN",
    }


def test_any_admin_can_list_plans(api_client, support_admin):
    resp = _bearer(api_client, support_admin).get(PLANS)
    assert resp.status_code == 200
    assert len(resp.json()) == 4


def test_list_excludes_archived_by_default(api_client, support_admin):
    Plan.objects.filter(key="CHAIN").update(archived=True)
    resp = _bearer(api_client, support_admin).get(PLANS)
    assert {p["key"] for p in resp.json()} == {"FREE", "STARTER", "GROWTH"}


def test_list_include_archived_param(api_client, support_admin):
    Plan.objects.filter(key="CHAIN").update(archived=True)
    resp = _bearer(api_client, support_admin).get(PLANS, {"include_archived": "true"})
    assert {p["key"] for p in resp.json()} == {"FREE", "STARTER", "GROWTH", "CHAIN"}


def test_any_admin_can_view_plan_detail(api_client, support_admin):
    resp = _bearer(api_client, support_admin).get(f"{PLANS}/GROWTH")
    assert resp.status_code == 200
    assert resp.json()["max_cards"] == 10


# ── role gate on mutations ─────────────────────────────────────────────────────
def test_support_admin_cannot_create_plan(api_client, support_admin):
    resp = _bearer(api_client, support_admin).post(
        PLANS, {"key": "ENTERPRISE", "name": "Enterprise", "price_egp": "1999"}, format="json"
    )
    assert resp.status_code == 403


def test_support_admin_cannot_patch_plan(api_client, support_admin):
    resp = _bearer(api_client, support_admin).patch(
        f"{PLANS}/GROWTH", {"price_egp": "999"}, format="json"
    )
    assert resp.status_code == 403


def test_unauthenticated_request_rejected(api_client):
    assert api_client.get(PLANS).status_code == 401


# ── finance/super-admin mutations ─────────────────────────────────────────────
def test_finance_admin_can_create_plan(api_client, finance_admin):
    resp = _bearer(api_client, finance_admin).post(
        PLANS,
        {
            "key": "ENTERPRISE",
            "name": "Enterprise",
            "price_egp": "1999",
            "max_cards": None,
            "max_locations": None,
            "max_staff": None,
            "max_customers": None,
            "export": True,
            "api": True,
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert Plan.objects.filter(key="ENTERPRISE").exists()
    assert AdminAuditLog.objects.filter(action="plan.create", target_id="ENTERPRISE").exists()


def test_duplicate_plan_key_rejected(api_client, finance_admin):
    resp = _bearer(api_client, finance_admin).post(
        PLANS, {"key": "GROWTH", "name": "Dup", "price_egp": "1"}, format="json"
    )
    assert resp.status_code == 400


def test_super_admin_can_patch_plan_price(api_client, super_admin):
    resp = _bearer(api_client, super_admin).patch(
        f"{PLANS}/STARTER", {"price_egp": "349"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["price_egp"] == "349.00"
    log = AdminAuditLog.objects.get(action="plan.update", target_id="STARTER")
    assert log.metadata["before"]["price_egp"] == "299.00"
    assert log.metadata["after"]["price_egp"] == "349.00"


def test_patch_cannot_change_key(api_client, super_admin):
    resp = _bearer(api_client, super_admin).patch(
        f"{PLANS}/STARTER", {"key": "RENAMED"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["key"] == "STARTER"
    assert Plan.objects.filter(key="STARTER").exists()


def test_archiving_a_plan_is_audited_distinctly(api_client, super_admin):
    resp = _bearer(api_client, super_admin).patch(
        f"{PLANS}/CHAIN", {"archived": True}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["archived"] is True
    assert AdminAuditLog.objects.filter(action="plan.archive", target_id="CHAIN").exists()


# ── entitlements integration: edits actually gate live ────────────────────────
def test_editing_plan_limit_changes_live_entitlements(api_client, super_admin, merchant):
    services.activate_plan(merchant, PlanTier.STARTER)
    assert entitlements.check(merchant, "api") is False  # Starter has no API access

    resp = _bearer(api_client, super_admin).patch(f"{PLANS}/STARTER", {"api": True}, format="json")
    assert resp.status_code == 200
    assert entitlements.check(merchant, "api") is True


def test_editing_plan_price_updates_the_checkout_price(api_client, super_admin):
    """Editing a price in the admin panel must change what checkout actually
    charges — the subscribe/billing flow reads ``plan_price`` (DB-backed)."""
    resp = _bearer(api_client, super_admin).patch(
        f"{PLANS}/STARTER", {"price_egp": "349"}, format="json"
    )
    assert resp.status_code == 200
    assert plan_price("STARTER") == Decimal("349.00")


def test_archived_plan_still_resolves_its_own_db_limits(merchant):
    """Archiving hides a plan from the catalogue listing but must NOT change how an
    existing subscriber's limits resolve — the archived row's own DB value wins,
    not the hardcoded seed (CHAIN's seed is unlimited cards)."""
    services.activate_plan(merchant, PlanTier.CHAIN)
    Plan.objects.filter(key="CHAIN").update(archived=True, max_cards=1)
    invalidate_plan_cache()
    assert entitlements.check(merchant, "max_cards") is True  # 0 < 1
    factories.CardFactory(merchant=merchant)
    assert entitlements.check(merchant, "max_cards") is False  # 1 == 1 -> DB limit honored
