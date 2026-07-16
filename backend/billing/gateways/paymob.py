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
from billing.plans import PAYMOB_FREQUENCIES

_API_BASE = "https://accept.paymob.com"

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

    # ── auth ──────────────────────────────────────────────────────────────────
    def _auth_token(self, client: httpx.Client) -> str:
        """A legacy Accept auth token (valid ~1h), derived from ``API_KEY``.

        This is *not* ``SECRET_KEY``: the Intention API takes the secret key,
        but ``api/auth/tokens`` and the subscription-plan endpoints take this.
        """
        resp = client.post(f"{_API_BASE}/api/auth/tokens", json={"api_key": self.cfg["API_KEY"]})
        resp.raise_for_status()
        return str(resp.json()["token"])

    # ── subscription plans (ops / management command) ─────────────────────────
    def create_subscription_plan(
        self,
        *,
        name: str,
        amount_egp: Decimal,
        frequency: int,
        webhook_url: str,
        reminder_days: str = "",
        retrial_days: str = "",
        is_active: bool = True,
    ) -> str:
        """Create a Paymob Subscription Plan; return its id.

        The recurring deductions this plan drives are unattended, so it must
        carry the **Moto** integration — the 3DS card integration would demand
        an authentication the renewal can never satisfy. ``frequency`` is in
        days and Paymob only accepts a value from its closed enum.
        """
        if frequency not in PAYMOB_FREQUENCIES:
            raise ValueError(
                f"frequency {frequency} is not one of Paymob's "
                f"{sorted(PAYMOB_FREQUENCIES)} — the API would reject it."
            )
        if not self.cfg.get("API_KEY", ""):
            # Stub mode — deterministic, no network (local/CI).
            return f"paymob-stub-plan-{frequency}-{name.lower().replace(' ', '-')}"

        moto_id = self.cfg.get("MOTO_INTEGRATION_ID", "")
        if not moto_id:
            raise ValueError(
                "PAYMOB_MOTO_INTEGRATION_ID is not configured — a subscription "
                "plan built on the 3DS card integration cannot auto-deduct."
            )

        body: dict[str, Any] = {
            "name": name[:200],  # Paymob caps the name at 200 chars
            "frequency": frequency,
            "amount_cents": int(amount_egp * 100),
            # The plan's amount stays authoritative, so a discounted or 1 EGP
            # first charge never becomes the renewal price. Also a hard
            # requirement for deferring the first deduction: Paymob only honours
            # ``subscription_start_date`` while this is false.
            "use_transaction_amount": False,
            "is_active": is_active,
            # Paymob names this field ``integration``, not ``integration_id``.
            "integration": int(moto_id),
            "webhook_url": webhook_url,
            "plan_type": "rent",
        }
        if reminder_days:
            body["reminder_days"] = reminder_days
        if retrial_days:
            body["retrial_days"] = retrial_days

        with httpx.Client(timeout=20.0) as client:
            token = self._auth_token(client)
            resp = client.post(
                f"{_API_BASE}/api/acceptance/subscription-plans",
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            # Paymob returns the id as a number; we store it as a string.
            return str(resp.json()["id"])

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
            token = self._auth_token(client)
            order = client.post(
                f"{_API_BASE}/api/ecommerce/orders",
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
                f"{_API_BASE}/api/acceptance/payment_keys",
                json={
                    "auth_token": token,
                    "amount_cents": amount_cents,
                    "currency": "EGP",
                    "order_id": order["id"],
                    "integration_id": self.cfg.get("CARD_INTEGRATION_ID", ""),
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
        url = f"{_API_BASE}/api/acceptance/iframes/{iframe_id}?payment_token={pay_key}"
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
