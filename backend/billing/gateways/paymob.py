"""Paymob adapter — hosted-checkout creation + HMAC webhook verification.

The webhook HMAC follows Paymob's documented scheme: HMAC-SHA512 over an ordered
concatenation of transaction fields, keyed by ``PAYMOB_HMAC_SECRET``, compared
against the ``hmac`` query parameter. When ``PAYMOB_API_KEY`` is unset the
adapter runs in stub mode (deterministic checkout URL, no network) so local dev
and CI never call the real gateway — the same seam the tests fake.
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

# Order of fields Paymob concatenates before HMAC-SHA512 (their docs §webhooks).
_HMAC_FIELDS = (
    "amount_cents",
    "created_at",
    "currency",
    "error_occured",
    "has_parent_transaction",
    "id",
    "integration_id",
    "is_3d_secure",
    "is_auth",
    "is_capture",
    "is_refunded",
    "is_standalone_payment",
    "is_voided",
    "order.id",
    "owner",
    "pending",
    "source_data.pan",
    "source_data.sub_type",
    "source_data.type",
    "success",
)


def _config() -> dict[str, str]:
    return getattr(settings, "BILLING", {}).get("PAYMOB", {})


class PaymobGateway:
    provider = "paymob"

    def __init__(self) -> None:
        self.cfg = _config()

    # ── checkout ──────────────────────────────────────────────────────────────
    def create_checkout(
        self, *, merchant_id: str, plan: str, amount_egp: Decimal, customer_email: str = ""
    ) -> CheckoutSession:
        api_key = self.cfg.get("API_KEY", "")
        if not api_key:
            # Stub mode — deterministic, no network (local/CI).
            ref = f"paymob-stub-{merchant_id}-{plan}"
            return CheckoutSession(
                checkout_url=f"{settings.BASE_URL}/billing/checkout/paymob?ref={ref}",
                gateway_ref=ref,
            )

        amount_cents = int(amount_egp * 100)
        with httpx.Client(timeout=20.0) as client:
            token = client.post(
                "https://accept.paymob.com/api/auth/tokens", json={"api_key": api_key}
            ).json()["token"]
            order = client.post(
                "https://accept.paymob.com/api/ecommerce/orders",
                json={
                    "auth_token": token,
                    "amount_cents": amount_cents,
                    "currency": "EGP",
                    "delivery_needed": False,
                    "items": [],
                },
            ).json()
            order_id = str(order["id"])
            pay_key = client.post(
                "https://accept.paymob.com/api/acceptance/payment_keys",
                json={
                    "auth_token": token,
                    "amount_cents": amount_cents,
                    "currency": "EGP",
                    "order_id": order["id"],
                    "integration_id": self.cfg.get("INTEGRATION_ID", ""),
                    "billing_data": {
                        "email": customer_email or "na@kasbana.net",
                        "first_name": "Kasbana",
                        "last_name": "Merchant",
                        "phone_number": "+200000000000",
                        "country": "EG",
                        "city": "NA",
                        "street": "NA",
                        "building": "NA",
                        "floor": "NA",
                        "apartment": "NA",
                    },
                },
            ).json()["token"]
        iframe_id = self.cfg.get("IFRAME_ID", "")
        url = (
            f"https://accept.paymob.com/api/acceptance/iframes/{iframe_id}?payment_token={pay_key}"
        )
        return CheckoutSession(checkout_url=url, gateway_ref=order_id)

    # ── webhook ───────────────────────────────────────────────────────────────
    def verify_and_parse(self, *, headers: dict[str, str], body: bytes) -> WebhookEvent:
        payload = json.loads(body or b"{}")
        obj = payload.get("obj", payload)
        received = str(payload.get("hmac", "") or _header(headers, "hmac"))
        self._verify_hmac(obj, received)

        success = bool(obj.get("success")) and not bool(obj.get("error_occured"))
        order = obj.get("order", {})
        gateway_ref = str(order.get("id", obj.get("order.id", "")))
        amount = obj.get("amount_cents")
        amount_egp = _to_egp(Decimal(str(amount)) / 100) if amount is not None else None
        kind = "success" if success else "failed"
        if obj.get("is_voided") or obj.get("is_refunded"):
            kind = "canceled"
        return WebhookEvent(
            provider=self.provider,
            kind=kind,
            gateway_ref=gateway_ref,
            amount_egp=amount_egp,
        )

    def _verify_hmac(self, obj: dict[str, Any], received: str) -> None:
        secret = self.cfg.get("HMAC_SECRET", "")
        if not secret:
            # No secret configured (stub/dev) — accept, but never in prod (the
            # secret is always set on staging/prod via env).
            if not settings.DEBUG:
                raise WebhookVerificationError("PAYMOB_HMAC_SECRET is not configured.")
            return
        concatenated = "".join(_flatten(obj, field) for field in _HMAC_FIELDS)
        expected = hmac.new(secret.encode(), concatenated.encode(), hashlib.sha512).hexdigest()
        if not hmac.compare_digest(expected, received):
            raise WebhookVerificationError("Paymob HMAC mismatch.")


def _flatten(obj: dict[str, Any], dotted: str) -> str:
    """Resolve a possibly dotted key (``order.id``) into its string value."""
    cur: Any = obj
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = None
    if isinstance(cur, bool):
        return "true" if cur else "false"
    return "" if cur is None else str(cur)


def _header(headers: dict[str, str], name: str) -> str:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return ""
