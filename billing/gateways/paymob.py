"""Paymob adapter — checkout creation, subscription actions, HMAC verification.

Two auth schemes are in play and they are not interchangeable:

- the **Intention API** (``v1/intention/``) takes ``SECRET_KEY`` prefixed with
  the literal word ``Token``;
- the **subscription** endpoints (plans, suspend/resume/cancel) take a ``Bearer``
  auth token minted from ``API_KEY`` via ``api/auth/tokens``, valid ~1 hour.

Two HMAC schemes likewise share ``PAYMOB_HMAC_SECRET`` but not their formula: a
*transaction* callback signs an ordered 19-field concatenation and delivers the
digest as a query param, while a *subscription* callback signs only
``"{trigger_type}for{subscription_data.id}"`` and puts it in the body.

Each entry point stubs out when the credential it needs is unset (deterministic,
no network) so local dev and CI never call the real gateway.
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
    SubscriptionEvent,
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

    # ── subscription actions ──────────────────────────────────────────────────
    def suspend_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Stop the next auto-deduction, reversibly. What a cancel-request calls:
        the merchant keeps access to the period they paid for, and can resume."""
        return self._subscription_action(subscription_id, "suspend")

    def resume_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Undo a suspend — deductions restart on the next billing date."""
        return self._subscription_action(subscription_id, "resume")

    def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Close the subscription permanently. Not resumable — prefer
        ``suspend_subscription`` unless the period has actually lapsed."""
        return self._subscription_action(subscription_id, "cancel")

    def _subscription_action(self, subscription_id: str, action: str) -> dict[str, Any]:
        if not subscription_id:
            raise ValueError(f"Cannot {action} a subscription without a Paymob subscription id.")
        if not self.cfg.get("API_KEY", ""):
            return {"stub": True, "action": action, "id": subscription_id}
        with httpx.Client(timeout=20.0) as client:
            token = self._auth_token(client)
            resp = client.post(
                f"{_API_BASE}/api/acceptance/subscriptions/{subscription_id}/{action}",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return dict(resp.json())

    # ── checkout ──────────────────────────────────────────────────────────────
    def create_checkout(
        self,
        *,
        merchant_id: str,
        plan: str,
        amount_egp: Decimal,
        customer_email: str = "",
        subscription_plan_id: str = "",
        subscription_start_date: str = "",
    ) -> CheckoutSession:
        """Create a payment Intention and return its Unified Checkout URL.

        With ``subscription_plan_id`` set, the one 3DS charge the customer
        completes here doubles as the linking transaction: Paymob saves the card
        and attaches a recurring subscription to it. ``subscription_start_date``
        (``YYYY-MM-DD``) defers the first real deduction — that's the card-upfront
        trial, where this charge is 1 EGP and the plan price hits at day 14.
        Paymob only honours it while the plan has ``use_transaction_amount``
        false, which ``create_subscription_plan`` guarantees.
        """
        if not self.cfg.get("SECRET_KEY", ""):
            # Stub mode — deterministic, no network (local/CI).
            ref = f"paymob-stub-{merchant_id}-{plan}"
            return CheckoutSession(
                checkout_url=f"{settings.BASE_URL}/billing/checkout/paymob?ref={ref}",
                gateway_ref=ref,
            )

        amount_cents = int(amount_egp * 100)
        body: dict[str, Any] = {
            "amount": amount_cents,
            "currency": "EGP",
            # The 3DS card integration, NOT the Moto one: this charge needs the
            # customer present to authenticate, which is what saves the card.
            "payment_methods": [int(self.cfg["CARD_INTEGRATION_ID"])],
            "items": [
                {"name": f"Stampn {plan}", "amount": amount_cents, "quantity": 1},
            ],
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
            # Echoed back in the callback's claims — lets a webhook be traced to
            # a merchant even if the gateway_ref lookup ever misses.
            "extras": {"merchant_id": merchant_id, "plan": plan},
            "notification_url": f"{settings.BASE_URL}/api/v1/billing/webhook/paymob",
            "redirection_url": f"{settings.DASHBOARD_BASE_URL}/billing",
        }
        if subscription_plan_id:
            body["subscription_plan_id"] = int(subscription_plan_id)
        if subscription_start_date:
            body["subscription_start_date"] = subscription_start_date

        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{_API_BASE}/v1/intention/",
                json=body,
                # The Intention API takes the secret key prefixed with "Token" —
                # not the Bearer auth-token the subscription endpoints want.
                headers={"Authorization": f"Token {self.cfg['SECRET_KEY']}"},
            )
            resp.raise_for_status()
            intention = resp.json()

        client_secret = intention["client_secret"]
        url = (
            f"{_API_BASE}/unifiedcheckout/?publicKey={self.cfg['PUBLIC_KEY']}"
            f"&clientSecret={client_secret}"
        )
        # Keep the *order* id as gateway_ref: it's what the transaction callback
        # carries as order.id, which is how subscription_by_gateway_ref matches
        # an event back to a merchant.
        return CheckoutSession(checkout_url=url, gateway_ref=str(intention["intention_order_id"]))

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
            transaction_ref=str(obj.get("id", "") or ""),
        )

    def verify_and_parse_subscription_event(
        self, *, headers: dict[str, str], body: bytes
    ) -> SubscriptionEvent:
        """Verify + parse a *subscription*-lifecycle callback.

        Cannot reuse ``verify_and_parse``: this callback carries its ``hmac`` in
        the body (not the query string) and signs only two fields rather than
        the 19-field transaction concatenation. Same secret, different scheme.
        """
        payload = json.loads(body or b"{}")
        data = payload.get("subscription_data") or {}
        trigger_type = str(payload.get("trigger_type", ""))
        subscription_id = str(data.get("id", ""))
        received = str(payload.get("hmac", "") or _header(headers, "hmac"))
        self._verify_subscription_hmac(trigger_type, subscription_id, received)

        amount = data.get("amount_cents")
        return SubscriptionEvent(
            provider=self.provider,
            trigger_type=trigger_type,
            subscription_id=subscription_id,
            plan_id=str(data.get("plan_id", "") or ""),
            state=str(data.get("state", "") or ""),
            amount_egp=_to_egp(Decimal(str(amount)) / 100) if amount is not None else None,
            next_billing=str(data.get("next_billing", "") or ""),
            initial_transaction=str(data.get("initial_transaction", "") or ""),
        )

    def _verify_subscription_hmac(
        self, trigger_type: str, subscription_id: str, received: str
    ) -> None:
        secret = self.cfg.get("HMAC_SECRET", "")
        if not secret:
            if not settings.DEBUG:
                raise WebhookVerificationError("PAYMOB_HMAC_SECRET is not configured.")
            return
        # Paymob signs the literal "{trigger_type}for{subscription_data.id}" —
        # e.g. "suspendedfor1264".
        concatenated = f"{trigger_type}for{subscription_id}"
        expected = hmac.new(secret.encode(), concatenated.encode(), hashlib.sha512).hexdigest()
        if not hmac.compare_digest(expected, received):
            raise WebhookVerificationError("Paymob subscription HMAC mismatch.")

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
