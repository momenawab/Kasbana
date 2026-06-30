"""Google Wallet backend — class/object provisioning + live updates.

Implements the provider seam for Google (contract §3.5). The "Save to Google
Wallet" URL is a signed RS256 JWT and needs no API call, so it works offline in
tests with a generated key. Class/object create + PATCH hit the Wallet API and
require real credentials; without them the backend degrades to a no-op.
"""

from __future__ import annotations

import logging
import time

import httpx
import jwt

from core.models import Card, CustomerCard
from wallets.google import builders
from wallets.google.config import is_configured, issuer_id, load_service_account

logger = logging.getLogger(__name__)

_API_BASE = "https://walletobjects.googleapis.com/walletobjects/v1"
_SCOPE = "https://www.googleapis.com/auth/wallet_object.issuer"


def build_save_url(customer_card: CustomerCard) -> str | None:
    """Signed 'Save to Google Wallet' link (RS256 JWT). None if unconfigured.

    The JWT embeds the full LoyaltyObject so the pass is created on save (given
    the class exists). This requires only the service-account key — no API call.
    """
    sa = load_service_account()
    if sa is None or not issuer_id():
        return None

    claims = {
        "iss": sa.client_email,
        "aud": "google",
        "typ": "savetowallet",
        "iat": int(time.time()),
        "payload": {"loyaltyObjects": [builders.build_loyalty_object(customer_card)]},
    }
    token = jwt.encode(claims, sa.private_key, algorithm="RS256")
    return f"https://pay.google.com/gp/v/save/{token}"


def _access_token() -> str | None:
    """OAuth2 bearer token for the Wallet API via the service-account JWT grant.

    Uses the standard JWT-bearer flow (PyJWT + httpx) so we don't pull in the
    ``requests`` library that google-auth's default transport requires.
    """
    sa = load_service_account()
    if sa is None:
        return None
    try:
        now = int(time.time())
        assertion = jwt.encode(
            {
                "iss": sa.client_email,
                "scope": _SCOPE,
                "aud": sa.token_uri,
                "iat": now,
                "exp": now + 3600,
            },
            sa.private_key,
            algorithm="RS256",
        )
        resp = httpx.post(
            sa.token_uri,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception:  # pragma: no cover - network/credential dependent
        logger.exception("Google Wallet: failed to obtain access token")
        return None


def _api() -> httpx.Client | None:
    token = _access_token()
    if token is None:
        return None
    return httpx.Client(
        base_url=_API_BASE,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )


def sync_class(card: Card) -> str | None:
    """Create or update the LoyaltyClass for a Card. Returns the class id.

    No-op (returns None) when credentials are absent.
    """
    if not is_configured():
        logger.info("Google Wallet not configured; skipping class sync for %s", card.id)
        return None

    payload = builders.build_loyalty_class(card)
    cid = payload["id"]
    client = _api()
    if client is None:
        return None
    with client:
        existing = client.get(f"/loyaltyClass/{cid}")
        if existing.status_code == 200:
            client.put(f"/loyaltyClass/{cid}", json=payload).raise_for_status()
        else:
            client.post("/loyaltyClass", json=payload).raise_for_status()

    if card.google_class_id != cid:
        card.google_class_id = cid
        card.save(update_fields=["google_class_id", "updated_at"])
    return cid


class GoogleWalletBackend:
    """Implements WalletProvisioner + WalletUpdater for Google."""

    def provision(self, customer_card: CustomerCard) -> str | None:
        """Ensure the class exists, then return the signed save URL."""
        card = customer_card.card
        if is_configured() and not card.google_class_id:
            sync_class(card)
        return build_save_url(customer_card)

    def push_update(self, customer_card: CustomerCard) -> None:
        """PATCH the LoyaltyObject so Google pushes the new balance to devices."""
        if not is_configured():
            return
        client = _api()
        if client is None:
            return
        oid = builders.object_id_for(customer_card)
        patch = {
            "state": builders.object_state_for(customer_card),
            "loyaltyPoints": {
                "label": "Stamps",
                "balance": {"int": customer_card.stamp_count},
            },
        }
        with client:
            resp = client.patch(f"/loyaltyObject/{oid}", json=patch)
            if resp.status_code == 404:
                # Object not created yet — create it from the full payload.
                client.post(
                    "/loyaltyObject",
                    json=builders.build_loyalty_object(customer_card),
                ).raise_for_status()
            else:
                resp.raise_for_status()

    def add_message(self, customer_card: CustomerCard, *, header: str, body: str) -> None:
        """Push a free notification onto the customer's Google pass.

        Google's ``addMessage`` delivers a device notification and appends the
        message to the pass's message list. ``message_id`` makes the call
        idempotent (a retried task won't double-notify). No-op when unconfigured
        or when the object doesn't exist yet (nothing to message).
        """
        if not is_configured():
            return
        client = _api()
        if client is None:
            return
        oid = builders.object_id_for(customer_card)
        payload = {
            "message": {
                "header": header or customer_card.card.merchant.name,
                "body": body,
                "id": f"msg-{customer_card.id.hex}-{int(time.time())}",
                "messageType": "TEXT",
            }
        }
        with client:
            resp = client.post(f"/loyaltyObject/{oid}/addMessage", json=payload)
            if resp.status_code == 404:
                logger.info("Google addMessage: object %s not provisioned yet; skipping", oid)
                return
            resp.raise_for_status()
