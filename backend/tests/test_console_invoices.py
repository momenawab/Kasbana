"""Admin invoice + manual-invoice tests (Phase 5).

Covers the role gate (reads open to any admin, mutations Finance/Super-admin),
the cross-tenant list/detail/filters, retry (incl. the FAILED-only guard and
that it uses the merchant's *current* plan/price), and the manual invoice
(mark-paid) flow.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from billing.models import Invoice
from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser
from core.enums import PlanTier, Role
from tests import factories

pytestmark = pytest.mark.django_db

INVOICES = "/api/admin/v1/invoices"


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
def test_any_admin_can_list_invoices_cross_tenant(api_client, support_admin, merchant):
    other = factories.MerchantFactory()
    Invoice.objects.create(merchant=merchant, amount_egp=Decimal("799"), status="paid")
    Invoice.objects.create(merchant=other, amount_egp=Decimal("299"), status="paid")

    resp = _bearer(api_client, support_admin).get(INVOICES)
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 2  # both merchants — cross-tenant


def test_filter_by_status(api_client, support_admin, merchant):
    Invoice.objects.create(merchant=merchant, amount_egp=Decimal("799"), status="paid")
    Invoice.objects.create(merchant=merchant, amount_egp=Decimal("799"), status="failed")

    resp = _bearer(api_client, support_admin).get(INVOICES, {"status": "failed"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["status"] == "failed"


def test_filter_by_merchant_id(api_client, support_admin, merchant):
    other = factories.MerchantFactory()
    Invoice.objects.create(merchant=merchant, amount_egp=Decimal("799"), status="paid")
    Invoice.objects.create(merchant=other, amount_egp=Decimal("299"), status="paid")

    resp = _bearer(api_client, support_admin).get(INVOICES, {"merchant_id": str(merchant.id)})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["merchant"]["id"] == str(merchant.id)


def test_invoice_detail(api_client, support_admin, merchant):
    invoice = Invoice.objects.create(
        merchant=merchant, amount_egp=Decimal("799"), status="paid", note="test note"
    )
    resp = _bearer(api_client, support_admin).get(f"{INVOICES}/{invoice.id}")
    assert resp.status_code == 200
    assert resp.json()["note"] == "test note"


def test_unauthenticated_request_rejected(api_client):
    assert api_client.get(INVOICES).status_code == 401


# ── retry ─────────────────────────────────────────────────────────────────────
def test_support_admin_cannot_retry(api_client, support_admin, merchant):
    invoice = Invoice.objects.create(merchant=merchant, amount_egp=Decimal("799"), status="failed")
    resp = _bearer(api_client, support_admin).post(f"{INVOICES}/{invoice.id}/retry")
    assert resp.status_code == 403


def test_retry_requires_failed_status(api_client, super_admin, merchant):
    invoice = Invoice.objects.create(merchant=merchant, amount_egp=Decimal("799"), status="paid")
    resp = _bearer(api_client, super_admin).post(f"{INVOICES}/{invoice.id}/retry")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVOICE_NOT_FAILED"


def test_retry_creates_new_checkout_at_current_plan_price(api_client, super_admin, merchant):
    from billing import services

    services.activate_plan(merchant, PlanTier.STARTER)  # current plan/price at retry time
    invoice = Invoice.objects.create(
        merchant=merchant, amount_egp=Decimal("799"), status="failed"  # stale/old amount
    )
    resp = _bearer(api_client, super_admin).post(f"{INVOICES}/{invoice.id}/retry")
    assert resp.status_code == 200
    assert resp.json()["checkout_url"].startswith("http")

    from billing.models import Subscription

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.pending_plan == PlanTier.STARTER  # retried at the CURRENT plan, not the old invoice
    assert AdminAuditLog.objects.filter(action="invoice.retry", target_id=str(invoice.id)).exists()


def test_retry_of_a_first_subscribe_failure_uses_pending_plan_not_free(
    api_client, super_admin, merchant
):
    """A merchant still TRIALING (never activated a paid plan — sub.plan
    defaults to FREE/0) whose first checkout attempt failed must be retried at
    the plan they were actually trying to buy (pending_plan), not FREE."""
    from billing import services
    from billing.models import Subscription
    from billing.plans import BillingStatus

    services.begin_checkout(merchant, plan=PlanTier.GROWTH, provider="paymob", gateway_ref="r1")
    invoice = Invoice.objects.create(
        merchant=merchant, amount_egp=Decimal("0"), status="failed", provider="paymob"
    )
    sub = Subscription.objects.get(merchant=merchant)
    assert sub.status == BillingStatus.TRIALING
    assert sub.plan == PlanTier.FREE  # never activated — the trap this test guards against

    resp = _bearer(api_client, super_admin).post(f"{INVOICES}/{invoice.id}/retry")
    assert resp.status_code == 200
    sub.refresh_from_db()
    assert sub.pending_plan == PlanTier.GROWTH  # retried at GROWTH, not FREE/0


# ── manual invoice (mark-paid) ──────────────────────────────────────────────────
def test_support_admin_cannot_create_manual_invoice(api_client, support_admin, merchant):
    resp = _bearer(api_client, support_admin).post(
        f"/api/admin/v1/merchants/{merchant.id}/invoices", {"amount_egp": "500"}, format="json"
    )
    assert resp.status_code == 403


def test_finance_admin_creates_manual_paid_invoice_by_default(api_client, finance_admin, merchant):
    resp = _bearer(api_client, finance_admin).post(
        f"/api/admin/v1/merchants/{merchant.id}/invoices",
        {"amount_egp": "500", "note": "bank transfer"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["status"] == "paid"
    assert resp.json()["note"] == "bank transfer"
    invoice = Invoice.objects.get(merchant=merchant)
    assert invoice.gateway_ref == ""  # manual — no gateway
    assert AdminAuditLog.objects.filter(
        action="invoice.create_manual", target_id=str(invoice.id)
    ).exists()


def test_manual_invoice_can_be_recorded_pending(api_client, finance_admin, merchant):
    resp = _bearer(api_client, finance_admin).post(
        f"/api/admin/v1/merchants/{merchant.id}/invoices",
        {"amount_egp": "500", "status": "pending"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"


def test_manual_invoices_are_not_deduplicated(api_client, finance_admin, merchant):
    """Each manual entry creates a new row — unlike gateway webhooks, there's no
    gateway_ref to dedupe on, and an admin may legitimately record two separate
    offline payments of the same amount."""
    url = f"/api/admin/v1/merchants/{merchant.id}/invoices"
    _bearer(api_client, finance_admin).post(url, {"amount_egp": "500"}, format="json")
    _bearer(api_client, finance_admin).post(url, {"amount_egp": "500"}, format="json")
    assert Invoice.objects.filter(merchant=merchant).count() == 2


def test_dunning_notify_sends_email_to_owner(api_client, super_admin, merchant, mailoutbox):
    factories.StaffUserFactory(merchant=merchant, role=Role.OWNER)
    resp = _bearer(api_client, super_admin).post(
        f"/api/admin/v1/merchants/{merchant.id}/dunning/notify", {}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["sent"] is True
    assert len(mailoutbox) == 1
    assert AdminAuditLog.objects.filter(
        action="dunning.notify", target_id=str(merchant.id)
    ).exists()
