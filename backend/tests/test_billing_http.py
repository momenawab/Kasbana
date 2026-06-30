"""Tests for billing HTTP endpoints + gateway webhooks (Phase 1.7).

Covers GET /billing, subscribe (checkout via faked gateway), invoices, cancel,
and the Paymob/Fawry webhook → activate_plan/lock round-trip. The gateway
adapters are faked (stub mode) so no real HTTP is made.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from billing.models import Invoice, Subscription
from billing.plans import BillingStatus
from core.enums import PlanTier, Role
from tests import factories

pytestmark = pytest.mark.django_db


def _client_for(role, merchant):
    from rest_framework_simplejwt.tokens import RefreshToken

    staff = factories.StaffUserFactory(merchant=merchant, role=role)
    client = APIClient()
    access = RefreshToken.for_user(staff.user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client, staff


# ── GET /billing ──────────────────────────────────────────────────────────────
def test_billing_state_during_trial(merchant):
    client, _ = _client_for(Role.OWNER, merchant)
    resp = client.get("/api/v1/billing")
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "trial"
    assert body["trial_ends_at"] is not None
    # Trial = Growth-level access, so the trial price reflects Growth.
    assert Decimal(str(body["price_egp"])) == Decimal("799")
    assert body["usage"]["whatsapp_used"] == 0
    assert body["usage"]["whatsapp_quota"] == 2000


def test_billing_state_requires_admin(merchant):
    client, _ = _client_for(Role.SCANNER, merchant)
    resp = client.get("/api/v1/billing")
    assert resp.status_code == 403


# ── subscribe ─────────────────────────────────────────────────────────────────
def test_subscribe_returns_checkout_url_and_records_pending(merchant):
    client, _ = _client_for(Role.OWNER, merchant)
    resp = client.post("/api/v1/billing/subscribe", {"plan": "growth"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["checkout_url"].startswith("http")

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.pending_plan == PlanTier.GROWTH
    assert sub.provider == "paymob"
    assert sub.gateway_ref


def test_subscribe_rejects_non_owner(merchant):
    client, _ = _client_for(Role.ADMIN, merchant)
    resp = client.post("/api/v1/billing/subscribe", {"plan": "growth"}, format="json")
    assert resp.status_code == 403


def test_subscribe_validates_plan(merchant):
    client, _ = _client_for(Role.OWNER, merchant)
    resp = client.post("/api/v1/billing/subscribe", {"plan": "bogus"}, format="json")
    assert resp.status_code == 400


# ── webhook round-trip: trial → paid → cancel ─────────────────────────────────
def _paymob_body(gateway_ref: str, *, success: bool, amount_cents: int = 79900):
    # DEBUG-mode webhooks skip HMAC, so the signature can be omitted.
    return json.dumps(
        {
            "obj": {
                "success": success,
                "error_occured": not success,
                "amount_cents": amount_cents,
                "order": {"id": gateway_ref},
            }
        }
    ).encode()


def test_paymob_webhook_activates_plan(settings, merchant):
    settings.DEBUG = True  # skip HMAC in the faked webhook
    client, _ = _client_for(Role.OWNER, merchant)
    client.post("/api/v1/billing/subscribe", {"plan": "growth"}, format="json")
    sub = Subscription.objects.get(merchant=merchant)

    resp = client.post(
        "/api/v1/billing/webhook/paymob",
        data=_paymob_body(sub.gateway_ref, success=True),
        content_type="application/json",
    )
    assert resp.status_code == 200

    sub.refresh_from_db()
    assert sub.status == BillingStatus.ACTIVE
    assert sub.plan == PlanTier.GROWTH
    merchant.refresh_from_db()
    assert merchant.plan == PlanTier.GROWTH
    # A paid invoice was recorded.
    invoice = Invoice.objects.get(merchant=merchant)
    assert invoice.status == "paid"
    assert invoice.amount_egp == Decimal("799.00")


def test_paymob_webhook_failed_payment_records_failed_invoice(settings, merchant):
    settings.DEBUG = True
    client, _ = _client_for(Role.OWNER, merchant)
    client.post("/api/v1/billing/subscribe", {"plan": "growth"}, format="json")
    sub = Subscription.objects.get(merchant=merchant)

    resp = client.post(
        "/api/v1/billing/webhook/paymob",
        data=_paymob_body(sub.gateway_ref, success=False),
        content_type="application/json",
    )
    assert resp.status_code == 200
    sub.refresh_from_db()
    assert sub.status == BillingStatus.TRIALING  # access unchanged
    assert Invoice.objects.get(merchant=merchant).status == "failed"


def test_paymob_webhook_replay_is_idempotent(settings, merchant):
    """A gateway retry of the same success event must not double-bill or
    re-activate — one paid invoice, plan active, both calls acknowledged."""
    settings.DEBUG = True
    client, _ = _client_for(Role.OWNER, merchant)
    client.post("/api/v1/billing/subscribe", {"plan": "growth"}, format="json")
    sub = Subscription.objects.get(merchant=merchant)
    body = _paymob_body(sub.gateway_ref, success=True)

    first = client.post(
        "/api/v1/billing/webhook/paymob", data=body, content_type="application/json"
    )
    second = client.post(
        "/api/v1/billing/webhook/paymob", data=body, content_type="application/json"
    )
    assert first.status_code == 200
    assert second.status_code == 200

    # Exactly one paid invoice despite the replay.
    assert Invoice.objects.filter(merchant=merchant, status="paid").count() == 1
    sub.refresh_from_db()
    assert sub.status == BillingStatus.ACTIVE
    assert sub.plan == PlanTier.GROWTH


def _fawry_body(*, ref: str, status: str = "PAID", amount: str = "799.00", sig: str = "bad"):
    return json.dumps(
        {
            "merchantRefNumber": ref,
            "orderStatus": status,
            "paymentAmount": amount,
            "paymentRefrenceNumber": "fawry-txn-1",
            "messageSignature": sig,
        }
    ).encode()


def test_fawry_webhook_bad_signature_rejected(settings, merchant):
    settings.DEBUG = False
    settings.BILLING = {**settings.BILLING, "FAWRY": {"SECURITY_KEY": "shh", "MERCHANT_CODE": "mc"}}
    client, _ = _client_for(Role.OWNER, merchant)
    resp = client.post(
        "/api/v1/billing/webhook/fawry",
        data=_fawry_body(ref="ref123", sig="not-the-real-signature"),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_paymob_webhook_bad_hmac_rejected(settings, merchant):
    settings.DEBUG = False
    settings.BILLING = {**settings.BILLING, "PAYMOB": {"HMAC_SECRET": "shh"}}
    client, _ = _client_for(Role.OWNER, merchant)
    resp = client.post(
        "/api/v1/billing/webhook/paymob",
        data=_paymob_body("ref123", success=True),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_cancel_locks_subscription(merchant):
    client, _ = _client_for(Role.OWNER, merchant)
    resp = client.post("/api/v1/billing/cancel", {"reason": "too pricey"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    sub = Subscription.objects.get(merchant=merchant)
    assert sub.status == BillingStatus.CANCELED


# ── invoices ──────────────────────────────────────────────────────────────────
def test_invoices_listing_is_tenant_scoped(merchant):
    other = factories.MerchantFactory()
    Invoice.objects.create(merchant=merchant, amount_egp=Decimal("799"), status="paid")
    Invoice.objects.create(merchant=other, amount_egp=Decimal("299"), status="paid")

    client, _ = _client_for(Role.ADMIN, merchant)
    resp = client.get("/api/v1/billing/invoices")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["status"] == "paid"
    assert "date" in results[0]
