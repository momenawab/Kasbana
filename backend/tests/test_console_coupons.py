"""Coupons, discounts & promotions tests (Phase 11).

Covers the Finance/Super-admin gate (Support 403 on writes), the discount math,
server-side cap enforcement (global + per-merchant), expiry + plan-scope, the
checkout integration (a code reduces the merchant's charge + records a capped
redemption), the redemption report, and admin apply-to-merchant grants.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from billing import coupons
from billing.models import Coupon, CouponRedemption, Subscription
from billing.plans import BillingStatus, plan_price
from billing.services import subscription_for
from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser
from core.enums import PlanTier, Role
from tests import factories

pytestmark = pytest.mark.django_db

BASE = "/api/admin/v1/coupons"


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


def _admin(admin):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return c


def _owner_client(merchant):
    """Subscribe requires OWNER — the default staff fixture is ADMIN."""
    staff = factories.StaffUserFactory(merchant=merchant, role=Role.OWNER)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(staff.user).access_token}")
    return c


def _coupon(**over):
    data = {"code": "SAVE20", "type": Coupon.Type.PERCENT, "value": Decimal("20")}
    data.update(over)
    return Coupon.objects.create(**data)


# ── discount math (unit) ────────────────────────────────────────────────────────
def test_percent_discount_math():
    c = _coupon(type=Coupon.Type.PERCENT, value=Decimal("25"))
    assert coupons.discounted_amount(c, Decimal("800")) == Decimal("600.00")


def test_fixed_discount_never_below_zero():
    c = _coupon(code="MINUS", type=Coupon.Type.FIXED, value=Decimal("1000"))
    assert coupons.discounted_amount(c, Decimal("299")) == Decimal("0.00")


# ── admin CRUD + role gate ──────────────────────────────────────────────────────
def test_support_cannot_create_coupon(api_client, support_admin):
    resp = _admin(support_admin).post(
        BASE, {"code": "x", "type": "percent", "value": "10"}, format="json"
    )
    assert resp.status_code == 403


def test_finance_creates_coupon_uppercased(api_client, finance_admin):
    resp = _admin(finance_admin).post(
        BASE, {"code": "spring25", "type": "percent", "value": "25"}, format="json"
    )
    assert resp.status_code == 201
    assert resp.json()["code"] == "SPRING25"
    assert AdminAuditLog.objects.filter(action="coupon.create").exists()


def test_duplicate_code_rejected(api_client, finance_admin):
    _coupon(code="DUP")
    resp = _admin(finance_admin).post(
        BASE, {"code": "dup", "type": "percent", "value": "10"}, format="json"
    )
    assert resp.status_code == 400


def test_any_admin_can_list(api_client, support_admin):
    _coupon()
    assert _admin(support_admin).get(BASE).status_code == 200


def test_deactivate_via_patch(api_client, finance_admin):
    _coupon(code="OFF")
    resp = _admin(finance_admin).patch(f"{BASE}/off", {"active": False}, format="json")
    assert resp.status_code == 200
    assert resp.json()["active"] is False


# ── validation ──────────────────────────────────────────────────────────────────
def test_validate_expired(merchant):
    c = _coupon(expires_at=timezone.now() - timedelta(days=1))
    with pytest.raises(coupons.CouponError) as e:
        coupons.validate(c, merchant)
    assert e.value.code == "COUPON_EXPIRED"


def test_validate_plan_scope(merchant):
    c = _coupon(plan_scope=[PlanTier.GROWTH])
    with pytest.raises(coupons.CouponError) as e:
        coupons.validate(c, merchant, PlanTier.STARTER)
    assert e.value.code == "COUPON_PLAN_SCOPE"


def test_global_cap_enforced(merchant):
    c = _coupon(max_redemptions=1)
    coupons.redeem(c, merchant, discount_egp=Decimal("10"))
    other = factories.MerchantFactory()
    # Production re-fetches the coupon per request (get_active); mirror that.
    c.refresh_from_db()
    with pytest.raises(coupons.CouponError) as e:
        coupons.validate(c, other)
    assert e.value.code == "COUPON_EXHAUSTED"


def test_per_merchant_once(merchant):
    c = _coupon(per_merchant_once=True)
    coupons.redeem(c, merchant, discount_egp=Decimal("10"))
    with pytest.raises(coupons.CouponError) as e:
        coupons.validate(c, merchant)
    assert e.value.code == "COUPON_ALREADY_USED"


def test_redeem_increments_count(merchant):
    c = _coupon()
    coupons.redeem(c, merchant, discount_egp=Decimal("10"))
    c.refresh_from_db()
    assert c.redemption_count == 1


# ── checkout integration (the DoD) ──────────────────────────────────────────────
def test_coupon_reduces_the_charge_at_subscribe(merchant):
    _coupon(code="HALF", type=Coupon.Type.PERCENT, value=Decimal("50"))
    resp = _owner_client(merchant).post(
        "/api/v1/billing/subscribe", {"plan": "growth", "coupon": "half"}, format="json"
    )
    assert resp.status_code == 200
    # A redemption was recorded for half of GROWTH's price.
    red = CouponRedemption.objects.get(merchant=merchant)
    assert red.discount_egp == (plan_price(PlanTier.GROWTH) / 2).quantize(Decimal("0.01"))


def test_subscribe_with_unknown_coupon_is_400(merchant):
    resp = _owner_client(merchant).post(
        "/api/v1/billing/subscribe", {"plan": "growth", "coupon": "nope"}, format="json"
    )
    assert resp.status_code == 400


def test_subscribe_without_coupon_unaffected(merchant):
    resp = _owner_client(merchant).post(
        "/api/v1/billing/subscribe", {"plan": "growth"}, format="json"
    )
    assert resp.status_code == 200
    assert not CouponRedemption.objects.filter(merchant=merchant).exists()


def test_exhausted_coupon_blocks_subscribe(merchant):
    c = _coupon(code="ONE", max_redemptions=1)
    coupons.redeem(c, factories.MerchantFactory(), discount_egp=Decimal("1"))
    resp = _owner_client(merchant).post(
        "/api/v1/billing/subscribe", {"plan": "growth", "coupon": "one"}, format="json"
    )
    assert resp.status_code == 400


# ── redemption report ───────────────────────────────────────────────────────────
def test_redemption_report(api_client, finance_admin, merchant):
    c = _coupon(code="REP")
    coupons.redeem(c, merchant, discount_egp=Decimal("40"), detail="GROWTH checkout")
    rows = _admin(finance_admin).get(f"{BASE}/rep/redemptions").json()
    assert len(rows) == 1
    assert rows[0]["merchant"]["id"] == str(merchant.id)
    assert rows[0]["detail"] == "GROWTH checkout"


# ── apply-to-merchant ───────────────────────────────────────────────────────────
def test_apply_trial_extension(api_client, finance_admin, merchant):
    _coupon(code="TRIAL30", type=Coupon.Type.TRIAL_EXTENSION, value=Decimal("30"))
    resp = _admin(finance_admin).post(
        f"/api/admin/v1/merchants/{merchant.id}/apply-coupon", {"code": "trial30"}, format="json"
    )
    assert resp.status_code == 200
    sub = subscription_for(merchant)
    assert sub.status == BillingStatus.TRIALING
    assert sub.trial_ends_at > timezone.now() + timedelta(days=29)
    assert AdminAuditLog.objects.filter(action="coupon.apply").exists()


def test_apply_free_months_sets_comp(api_client, finance_admin, merchant):
    _coupon(code="FREE3", type=Coupon.Type.FREE_MONTHS, value=Decimal("3"))
    resp = _admin(finance_admin).post(
        f"/api/admin/v1/merchants/{merchant.id}/apply-coupon", {"code": "free3"}, format="json"
    )
    assert resp.status_code == 200
    assert Subscription.objects.get(merchant=merchant).comp is True


def test_apply_percent_coupon_is_rejected(api_client, finance_admin, merchant):
    _coupon(code="PCT", type=Coupon.Type.PERCENT, value=Decimal("10"))
    resp = _admin(finance_admin).post(
        f"/api/admin/v1/merchants/{merchant.id}/apply-coupon", {"code": "pct"}, format="json"
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "COUPON_NOT_GRANTABLE"


def test_apply_requires_finance(api_client, support_admin, merchant):
    _coupon(code="TRIAL30", type=Coupon.Type.TRIAL_EXTENSION, value=Decimal("30"))
    resp = _admin(support_admin).post(
        f"/api/admin/v1/merchants/{merchant.id}/apply-coupon", {"code": "trial30"}, format="json"
    )
    assert resp.status_code == 403
