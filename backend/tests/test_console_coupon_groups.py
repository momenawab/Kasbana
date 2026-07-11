"""Coupon grouping tests (Phase 11 deferral — Phase E.2).

Covers the Finance/Super-admin write gate (Support/Read-only 403 on mutations),
the cursor-paginated list, the ``coupon_count`` rollup, assigning a coupon to a
group + filtering the coupon list by group, and the SET_NULL delete (a group's
coupons survive, just become ungrouped). Every mutation is audited.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from billing.models import Coupon, CouponGroup
from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser

pytestmark = pytest.mark.django_db

BASE = "/api/admin/v1"
GROUPS = f"{BASE}/coupon-groups"


@pytest.fixture
def finance_admin():
    a = AdminUser(email="finance@stampn.net", role=AdminRole.FINANCE)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def support_admin():
    a = AdminUser(email="support@stampn.net", role=AdminRole.SUPPORT)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def readonly_admin():
    a = AdminUser(email="ro@stampn.net", role=AdminRole.READ_ONLY)
    a.set_password("supersecret1")
    a.save()
    return a


def _admin(admin):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return c


def _make_coupon(code: str, group: CouponGroup | None = None) -> Coupon:
    return Coupon.objects.create(
        code=code, type=Coupon.Type.PERCENT, value=Decimal("10"), group=group
    )


# ── Create + gating ─────────────────────────────────────────────────────────


def test_finance_creates_group_and_audits(finance_admin):
    resp = _admin(finance_admin).post(GROUPS, {"name": "Summer 2026"}, format="json")
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Summer 2026"
    assert body["active"] is True
    assert body["coupon_count"] == 0
    assert CouponGroup.objects.filter(name="Summer 2026").exists()
    assert AdminAuditLog.objects.filter(action="coupon_group.create").exists()


def test_support_admin_cannot_create(support_admin):
    resp = _admin(support_admin).post(GROUPS, {"name": "Nope"}, format="json")
    assert resp.status_code == 403
    assert not CouponGroup.objects.exists()


def test_readonly_admin_reads_but_cannot_write(readonly_admin, finance_admin):
    CouponGroup.objects.create(name="Existing")
    ro = _admin(readonly_admin)
    assert ro.get(GROUPS).status_code == 200
    assert ro.post(GROUPS, {"name": "Blocked"}, format="json").status_code == 403


def test_blank_name_rejected(finance_admin):
    resp = _admin(finance_admin).post(GROUPS, {"name": "   "}, format="json")
    assert resp.status_code == 400


# ── List (paginated) + coupon_count ─────────────────────────────────────────


def test_list_is_paginated_and_counts_coupons(finance_admin):
    g = CouponGroup.objects.create(name="Coffee")
    _make_coupon("C1", group=g)
    _make_coupon("C2", group=g)
    _make_coupon("UNGROUPED")  # not in any group

    resp = _admin(finance_admin).get(GROUPS)
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body and "next" in body  # cursor-paginated envelope
    row = next(r for r in body["results"] if r["name"] == "Coffee")
    assert row["coupon_count"] == 2


# ── Coupon ↔ group assignment + filtering ───────────────────────────────────


def test_assign_coupon_to_group_on_create_and_filter(finance_admin):
    g = CouponGroup.objects.create(name="VIP")
    client = _admin(finance_admin)

    created = client.post(
        f"{BASE}/coupons",
        {"code": "VIP10", "type": "percent", "value": "10", "group": str(g.id)},
        format="json",
    )
    assert created.status_code == 201
    assert created.json()["group"] == str(g.id)

    _make_coupon("PLAIN")  # ungrouped

    # ?group=<id> narrows to the group; ?group=none excludes grouped coupons.
    in_group = client.get(f"{BASE}/coupons?group={g.id}").json()
    assert [c["code"] for c in in_group] == ["VIP10"]
    ungrouped = client.get(f"{BASE}/coupons?group=none").json()
    assert "PLAIN" in [c["code"] for c in ungrouped]
    assert "VIP10" not in [c["code"] for c in ungrouped]


def test_assign_coupon_to_group_via_patch(finance_admin):
    g = CouponGroup.objects.create(name="Retarget")
    _make_coupon("MOVE")
    resp = _admin(finance_admin).patch(f"{BASE}/coupons/MOVE", {"group": str(g.id)}, format="json")
    assert resp.status_code == 200
    assert resp.json()["group"] == str(g.id)


# ── Update + delete (SET_NULL) ──────────────────────────────────────────────


def test_patch_group_audits(finance_admin):
    g = CouponGroup.objects.create(name="Old")
    resp = _admin(finance_admin).patch(
        f"{GROUPS}/{g.id}", {"name": "New", "active": False}, format="json"
    )
    assert resp.status_code == 200
    g.refresh_from_db()
    assert g.name == "New" and g.active is False
    assert AdminAuditLog.objects.filter(action="coupon_group.update").exists()


def test_delete_group_detaches_coupons_not_deletes(finance_admin):
    g = CouponGroup.objects.create(name="Doomed")
    c = _make_coupon("KEEP", group=g)

    resp = _admin(finance_admin).delete(f"{GROUPS}/{g.id}")
    assert resp.status_code == 204
    assert not CouponGroup.objects.filter(pk=g.id).exists()

    c.refresh_from_db()
    assert c.group_id is None  # SET_NULL: coupon survives, just ungrouped
    log = AdminAuditLog.objects.get(action="coupon_group.delete")
    assert log.metadata["coupons_detached"] == 1


def test_support_admin_cannot_delete(support_admin):
    g = CouponGroup.objects.create(name="Guarded")
    assert _admin(support_admin).delete(f"{GROUPS}/{g.id}").status_code == 403
    assert CouponGroup.objects.filter(pk=g.id).exists()
