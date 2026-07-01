"""Admin dunning + reconciliation tests (Phase 5)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from billing import services
from billing.models import Invoice
from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminUser
from core.enums import PlanTier
from tests import factories

pytestmark = pytest.mark.django_db


@pytest.fixture
def super_admin():
    admin = AdminUser(email="super@stampn.net", name="Super", role=AdminRole.SUPER_ADMIN)
    admin.set_password("supersecret1")
    admin.save()
    return admin


def _bearer(client, admin):
    access = issue_admin_tokens(admin)["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


# ── dunning ──────────────────────────────────────────────────────────────────
def test_dunning_lists_past_due_merchants(api_client, super_admin, merchant):
    services.activate_plan(merchant, PlanTier.STARTER)
    services.lock(merchant, status="PAST_DUE")
    Invoice.objects.create(merchant=merchant, amount_egp=Decimal("299"), status="failed")

    resp = _bearer(api_client, super_admin).get("/api/admin/v1/billing/dunning")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["merchant"]["id"] == str(merchant.id)
    assert rows[0]["last_failed_invoice"]["amount_egp"] == "299.00"


def test_dunning_excludes_merchants_in_good_standing(api_client, super_admin, merchant):
    services.activate_plan(merchant, PlanTier.STARTER)  # ACTIVE, not PAST_DUE
    resp = _bearer(api_client, super_admin).get("/api/admin/v1/billing/dunning")
    assert resp.status_code == 200
    assert resp.json() == []


def test_failed_renewal_charge_flips_active_merchant_to_past_due(settings, merchant):
    """The webhook-driven dunning signal: a failed charge on an ACTIVE
    (paying) merchant must flip them to PAST_DUE so they surface in dunning."""
    import json

    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    from billing.models import Subscription
    from billing.plans import BillingStatus
    from core.enums import Role

    settings.DEBUG = True
    services.activate_plan(merchant, PlanTier.STARTER, provider="paymob", gateway_ref="sub_x")
    sub = Subscription.objects.get(merchant=merchant)

    staff = factories.StaffUserFactory(merchant=merchant, role=Role.OWNER)
    client = APIClient()
    access = RefreshToken.for_user(staff.user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    body = json.dumps(
        {
            "obj": {
                "success": False,
                "error_occured": True,
                "amount_cents": 29900,
                "order": {"id": sub.gateway_ref},  # matches the ACTIVE sub's gateway_ref
            }
        }
    ).encode()
    resp = client.post("/api/v1/billing/webhook/paymob", data=body, content_type="application/json")
    assert resp.status_code == 200
    sub.refresh_from_db()
    assert sub.status == BillingStatus.PAST_DUE


def test_trialing_merchant_failed_checkout_does_not_flip_to_past_due(settings, merchant):
    """A failed FIRST-subscribe charge (still trialing, never paid) must NOT be
    treated as past-due — they simply retry checkout."""
    import json

    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    from billing.models import Subscription
    from billing.plans import BillingStatus
    from core.enums import Role

    settings.DEBUG = True
    staff = factories.StaffUserFactory(merchant=merchant, role=Role.OWNER)
    client = APIClient()
    access = RefreshToken.for_user(staff.user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    client.post("/api/v1/billing/subscribe", {"plan": "growth"}, format="json")
    sub = Subscription.objects.get(merchant=merchant)

    body = json.dumps(
        {
            "obj": {
                "success": False,
                "error_occured": True,
                "amount_cents": 79900,
                "order": {"id": sub.gateway_ref},
            }
        }
    ).encode()
    client.post("/api/v1/billing/webhook/paymob", data=body, content_type="application/json")
    sub.refresh_from_db()
    assert sub.status == BillingStatus.TRIALING


# ── reconciliation ────────────────────────────────────────────────────────────
def test_reconciliation_flags_stale_pending_manual_invoice(api_client, super_admin, merchant):
    stale = Invoice.objects.create(
        merchant=merchant, amount_egp=Decimal("500"), status="pending", note="awaiting transfer"
    )
    stale.issued_at = timezone.now() - timedelta(days=10)
    stale.save(update_fields=["issued_at"])
    # A fresh pending manual invoice must NOT be flagged.
    Invoice.objects.create(merchant=merchant, amount_egp=Decimal("500"), status="pending")

    resp = _bearer(api_client, super_admin).get("/api/admin/v1/billing/reconciliation")
    assert resp.status_code == 200
    stale_ids = [row["id"] for row in resp.json()["stale_pending_invoices"]]
    assert str(stale.id) in stale_ids
    assert len(stale_ids) == 1


def test_reconciliation_flags_active_subscription_without_a_paid_invoice(
    api_client, super_admin, merchant
):
    services.activate_plan(merchant, PlanTier.STARTER, provider="paymob", gateway_ref="ref-1")
    # No PAID Invoice recorded for this merchant at all — a data-integrity gap.
    resp = _bearer(api_client, super_admin).get("/api/admin/v1/billing/reconciliation")
    assert resp.status_code == 200
    flagged = [row["merchant"]["id"] for row in resp.json()["active_without_paid_invoice"]]
    assert str(merchant.id) in flagged


def test_reconciliation_excludes_active_merchants_with_no_gateway_provider(
    api_client, super_admin, merchant
):
    """An admin can set a merchant ACTIVE directly (Phase 4's subscription PATCH)
    without ever routing through a real gateway checkout — ``provider`` stays
    blank, so there was never an expected paid invoice; must not be flagged."""
    services.activate_plan(merchant, PlanTier.STARTER)  # no provider= kwarg
    resp = _bearer(api_client, super_admin).get("/api/admin/v1/billing/reconciliation")
    assert resp.status_code == 200
    flagged = [row["merchant"]["id"] for row in resp.json()["active_without_paid_invoice"]]
    assert str(merchant.id) not in flagged
