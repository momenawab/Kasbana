"""Fawry adapter — checkout creation + SHA-256 signature verification.

Fawry signs its callbacks with SHA-256 over an ordered concatenation of the
transaction fields plus the merchant security key (their docs §server-callbacks).
As with Paymob, an unset ``FAWRY_MERCHANT_CODE`` puts the adapter in stub mode.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any

import httpx
from django.conf import settings

from billing.gateways.base import (
    CheckoutSession,
    WebhookEvent,
    WebhookVerificationError,
    _to_egp,
)

# Fawry payment-status callback statuses.
_PAID = {"PAID", "DELIVERED"}
_FAILED = {"FAILED", "DECLINED", "EXPIRED"}
_CANCELED = {"CANCELED", "REFUNDED"}


def _config() -> dict[str, str]:
    return getattr(settings, "BILLING", {}).get("FAWRY", {})


class FawryGateway:
    provider = "fawry"

    def __init__(self) -> None:
        self.cfg = _config()

    # ── checkout ──────────────────────────────────────────────────────────────
    def create_checkout(
        self, *, merchant_id: str, plan: str, amount_egp: Decimal, customer_email: str = ""
    ) -> CheckoutSession:
        merchant_code = self.cfg.get("MERCHANT_CODE", "")
        ref = f"{merchant_id}:{plan}"
        if not merchant_code:
            stub_ref = f"fawry-stub-{merchant_id}-{plan}"
            return CheckoutSession(
                checkout_url=f"{settings.BASE_URL}/billing/checkout/fawry?ref={stub_ref}",
                gateway_ref=stub_ref,
            )

        sig = self._sign(
            merchant_code,
            ref,
            customer_email,
            f"{amount_egp:.2f}",
            self.cfg.get("SECURITY_KEY", ""),
        )
        payload = {
            "merchantCode": merchant_code,
            "merchantRefNum": ref,
            "customerEmail": customer_email or "na@kasbana.net",
            "amount": float(amount_egp),
            "currencyCode": "EGP",
            "description": f"Kasbana {plan} plan",
            "signature": sig,
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                "https://atfawry.fawrystaging.com/fawrypay-api/api/payments/init",
                json=payload,
            )
        checkout_url = resp.text.strip('"') if resp.status_code == 200 else ""
        return CheckoutSession(checkout_url=checkout_url, gateway_ref=ref)

    # ── webhook ───────────────────────────────────────────────────────────────
    def verify_and_parse(self, *, headers: dict[str, str], body: bytes) -> WebhookEvent:
        payload = json.loads(body or b"{}")
        self._verify_signature(payload)

        status = str(payload.get("orderStatus", "")).upper()
        ref = str(payload.get("merchantRefNumber", payload.get("merchantRefNum", "")))
        amount = payload.get("paymentAmount", payload.get("orderAmount"))
        amount_egp = _to_egp(amount) if amount is not None else None

        if status in _PAID:
            kind = "success"
        elif status in _CANCELED:
            kind = "canceled"
        elif status in _FAILED:
            kind = "failed"
        else:
            kind = "ignored"

        merchant_id, _, plan = ref.partition(":")
        return WebhookEvent(
            provider=self.provider,
            kind=kind,
            gateway_ref=ref,
            merchant_id=merchant_id or None,
            plan=plan or None,
            amount_egp=amount_egp,
        )

    def _verify_signature(self, payload: dict[str, Any]) -> None:
        security_key = self.cfg.get("SECURITY_KEY", "")
        received = str(payload.get("messageSignature", ""))
        if not security_key:
            if not settings.DEBUG:
                raise WebhookVerificationError("FAWRY_SECURITY_KEY is not configured.")
            return
        # Fawry callback signature: SHA-256 of fields + security key (docs).
        ref = str(payload.get("merchantRefNumber", payload.get("merchantRefNum", "")))
        order_amount = f"{Decimal(str(payload.get('paymentAmount', '0'))):.2f}"
        status = str(payload.get("orderStatus", ""))
        raw = (
            f"{self.cfg.get('MERCHANT_CODE', '')}{ref}"
            f"{payload.get('paymentRefrenceNumber', '')}{status}{order_amount}{security_key}"
        )
        expected = hashlib.sha256(raw.encode()).hexdigest()
        # Constant-time compare on the security boundary (matches Paymob's adapter).
        if not hmac.compare_digest(expected, received):
            raise WebhookVerificationError("Fawry signature mismatch.")

    @staticmethod
    def _sign(*parts: str) -> str:
        return hashlib.sha256("".join(parts).encode()).hexdigest()
