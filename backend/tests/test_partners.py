"""Partner / merchant-referral program tests (Phase E.1).

Covers the PARTNERS_MANAGE write gate (Support/Read-only 403), partner CRUD +
code/merchant uniqueness, manual + signup attribution (self/duplicate guards),
global-vs-override reward resolution, the grant_free_months primitive, and the
one-time conversion reward (both sides comped, idempotent, off when disabled).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from billing import services as billing
from billing.models import Subscription
from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser
from partners import services
from partners.models import Partner, PartnerProgramConfig, PartnerReferral
from tests import factories

pytestmark = pytest.mark.django_db

BASE = "/api/admin/v1"
PARTNERS = f"{BASE}/partners"


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


def _partner(code="REF10", **overrides):
    return Partner.objects.create(merchant=factories.MerchantFactory(), code=code, **overrides)


# ── CRUD + gating ───────────────────────────────────────────────────────────


def test_finance_creates_partner_and_audits(finance_admin):
    merchant = factories.MerchantFactory()
    resp = _admin(finance_admin).post(
        PARTNERS, {"merchant_id": str(merchant.id), "code": "vip"}, format="json"
    )
    assert resp.status_code == 201
    assert resp.json()["code"] == "vip"
    assert Partner.objects.filter(merchant=merchant, code="vip").exists()
    assert AdminAuditLog.objects.filter(action="partner.create").exists()


def test_support_admin_cannot_create(support_admin):
    merchant = factories.MerchantFactory()
    resp = _admin(support_admin).post(
        PARTNERS, {"merchant_id": str(merchant.id), "code": "NOPE"}, format="json"
    )
    assert resp.status_code == 403
    assert not Partner.objects.exists()


def test_readonly_reads_but_cannot_write(readonly_admin):
    _partner(code="EXIST")
    ro = _admin(readonly_admin)
    assert ro.get(PARTNERS).status_code == 200
    merchant = factories.MerchantFactory()
    assert (
        ro.post(PARTNERS, {"merchant_id": str(merchant.id), "code": "X"}, format="json").status_code
        == 403
    )


def test_duplicate_code_rejected(finance_admin):
    _partner(code="DUP")
    merchant = factories.MerchantFactory()
    resp = _admin(finance_admin).post(
        PARTNERS, {"merchant_id": str(merchant.id), "code": "dup"}, format="json"
    )
    assert resp.status_code == 400


def test_merchant_already_partner_rejected(finance_admin):
    p = _partner(code="ONE")
    resp = _admin(finance_admin).post(
        PARTNERS, {"merchant_id": str(p.merchant_id), "code": "TWO"}, format="json"
    )
    assert resp.status_code == 400


def test_patch_and_delete_partner(finance_admin):
    p = _partner(code="EDIT")
    client = _admin(finance_admin)
    patched = client.patch(
        f"{PARTNERS}/{p.id}", {"active": False, "partner_free_months_override": 3}, format="json"
    )
    assert patched.status_code == 200
    p.refresh_from_db()
    assert p.active is False and p.partner_free_months_override == 3
    assert AdminAuditLog.objects.filter(action="partner.update").exists()

    assert client.delete(f"{PARTNERS}/{p.id}").status_code == 204
    assert not Partner.objects.filter(pk=p.id).exists()
    assert AdminAuditLog.objects.filter(action="partner.delete").exists()


# ── Manual attribution ──────────────────────────────────────────────────────


def test_manual_attribution_and_guards(finance_admin):
    p = _partner(code="ATTR")
    client = _admin(finance_admin)
    referred = factories.MerchantFactory()

    ok = client.post(
        f"{PARTNERS}/{p.id}/referrals", {"merchant_id": str(referred.id)}, format="json"
    )
    assert ok.status_code == 201
    assert PartnerReferral.objects.filter(partner=p, referred_merchant=referred).exists()

    # a second attribution of the same merchant conflicts
    dup = client.post(
        f"{PARTNERS}/{p.id}/referrals", {"merchant_id": str(referred.id)}, format="json"
    )
    assert dup.status_code == 409

    # the partner cannot refer itself
    self_ref = client.post(
        f"{PARTNERS}/{p.id}/referrals", {"merchant_id": str(p.merchant_id)}, format="json"
    )
    assert self_ref.status_code == 409


def test_referrals_report(finance_admin):
    p = _partner(code="RPT")
    services.assign_admin(p, factories.MerchantFactory())
    resp = _admin(finance_admin).get(f"{PARTNERS}/{p.id}/referrals")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── Global config ───────────────────────────────────────────────────────────


def test_config_get_and_patch(finance_admin, support_admin):
    client = _admin(finance_admin)
    assert client.get(f"{BASE}/partner-config").json()["enabled"] is False
    patched = client.patch(
        f"{BASE}/partner-config",
        {"enabled": True, "partner_free_months": 2, "merchant_free_months": 1},
        format="json",
    )
    assert patched.status_code == 200
    assert PartnerProgramConfig.get_solo().enabled is True
    assert AdminAuditLog.objects.filter(action="partner_config.update").exists()
    # Support cannot change the config
    assert (
        _admin(support_admin)
        .patch(f"{BASE}/partner-config", {"enabled": False}, format="json")
        .status_code
        == 403
    )


# ── Reward resolution + attribution service ─────────────────────────────────


def test_resolved_config_override_and_active():
    cfg = PartnerProgramConfig.get_solo()
    cfg.enabled = True
    cfg.partner_free_months = 1
    cfg.merchant_free_months = 1
    cfg.save()

    p = _partner(code="OVR", partner_free_months_override=5)
    resolved = p.resolved_config()
    assert resolved.enabled is True
    assert resolved.partner_free_months == 5  # override wins
    assert resolved.merchant_free_months == 1  # falls back to global

    p.active = False
    assert p.resolved_config().enabled is False  # inactive partner never rewards


def test_attribute_signup_variants():
    p = _partner(code="SIGN")
    referred = factories.MerchantFactory()
    assert services.attribute_signup(referred, "sign") is not None  # case-insensitive
    assert services.attribute_signup(factories.MerchantFactory(), "unknown") is None
    assert services.attribute_signup(factories.MerchantFactory(), "") is None
    assert services.attribute_signup(p.merchant, "SIGN") is None  # self-referral


# ── grant_free_months primitive ─────────────────────────────────────────────


def test_grant_free_months_extends_period():
    m = factories.MerchantFactory()
    billing.grant_free_months(m, 2)
    sub = Subscription.objects.get(merchant=m)
    assert sub.current_period_end is not None
    assert sub.current_period_end > timezone.now() + timedelta(days=55)

    # extends from an existing future end, not from now
    future = timezone.now() + timedelta(days=200)
    sub.current_period_end = future
    sub.save()
    billing.grant_free_months(m, 1)
    sub.refresh_from_db()
    assert sub.current_period_end > future


def test_grant_free_months_zero_is_noop():
    m = factories.MerchantFactory()
    billing.grant_free_months(m, 0)
    assert Subscription.objects.get(merchant=m).current_period_end is None


# ── Conversion reward (the crux) ────────────────────────────────────────────


def _enable_program(partner_months=2, merchant_months=1):
    cfg = PartnerProgramConfig.get_solo()
    cfg.enabled = True
    cfg.partner_free_months = partner_months
    cfg.merchant_free_months = merchant_months
    cfg.save()


def test_conversion_grants_both_sides_once():
    _enable_program(partner_months=2, merchant_months=1)
    p = _partner(code="CONV")
    referred = factories.MerchantFactory()
    services.assign_admin(p, referred)

    services.on_merchant_converted(referred)

    referral = PartnerReferral.objects.get(referred_merchant=referred)
    assert referral.reward_granted is True
    assert referral.converted_at is not None
    assert referral.partner_months_granted == 2
    assert referral.merchant_months_granted == 1
    assert Subscription.objects.get(merchant=referred).current_period_end is not None
    partner_end = Subscription.objects.get(merchant=p.merchant).current_period_end
    assert partner_end is not None

    # a repeated webhook must not double-grant
    services.on_merchant_converted(referred)
    assert Subscription.objects.get(merchant=p.merchant).current_period_end == partner_end


def test_conversion_noop_when_disabled():
    # program left disabled (default)
    p = _partner(code="OFF")
    referred = factories.MerchantFactory()
    services.assign_admin(p, referred)
    services.on_merchant_converted(referred)
    assert PartnerReferral.objects.get(referred_merchant=referred).reward_granted is False


def test_conversion_noop_when_not_referred():
    m = factories.MerchantFactory()
    services.on_merchant_converted(m)  # no referral → nothing happens
    assert not Subscription.objects.filter(merchant=m).exists()


# ── Integration: signup capture + webhook conversion ────────────────────────

SIGNUP = {
    "business_name": "New Shop",
    "owner_name": "Owner",
    "email": "new@shop.test",
    "phone": "+201000000000",
    "password": "supersecret1",
    "consent": True,
}


def test_signup_with_referral_code_attributes():
    p = _partner(code="WELCOME")
    resp = APIClient().post(
        "/api/v1/auth/signup", {**SIGNUP, "referral_code": "welcome"}, format="json"
    )
    assert resp.status_code == 200
    referral = PartnerReferral.objects.get(partner=p)
    assert referral.attributed_via == PartnerReferral.Source.SIGNUP_CODE
    assert referral.referred_merchant.name == "New Shop"


def test_signup_without_code_creates_no_referral():
    resp = APIClient().post("/api/v1/auth/signup", SIGNUP, format="json")
    assert resp.status_code == 200
    assert not PartnerReferral.objects.exists()


def test_webhook_success_fires_reward():
    from decimal import Decimal

    from billing.gateways.base import WebhookEvent

    _enable_program(partner_months=2, merchant_months=1)
    p = _partner(code="HOOK")
    referred = factories.MerchantFactory()
    billing.subscription_for(referred)  # a real merchant has one from signup
    services.assign_admin(p, referred)

    event = WebhookEvent(
        provider="paymob",
        kind="success",
        gateway_ref="txn-123",
        merchant_id=str(referred.id),
        plan="GROWTH",
        amount_egp=Decimal("100"),
    )
    billing.apply_webhook_event(event)

    referral = PartnerReferral.objects.get(referred_merchant=referred)
    assert referral.reward_granted is True
    assert Subscription.objects.get(merchant=referred).current_period_end is not None
    assert Subscription.objects.get(merchant=p.merchant).current_period_end is not None
