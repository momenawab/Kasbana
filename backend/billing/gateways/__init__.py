"""Payment gateway adapters (Phase 1.7).

A thin ``PaymentGateway`` interface with a Paymob implementation. The adapter
owns two concerns: creating a hosted-checkout URL for ``subscribe`` and verifying
+ parsing the provider's webhook into a provider-agnostic ``WebhookEvent``.
Network calls go through ``httpx``; in tests the adapter is faked (no real HTTP)
— see ``tests/test_billing_http.py``.

Real credentials are wired on staging (``PAYMOB_API_KEY``); locally the gateway
runs in a deterministic stub mode when its keys are unset.
"""

from __future__ import annotations

from billing.gateways.base import PaymentGateway, WebhookEvent
from billing.gateways.paymob import PaymobGateway

# Active provider adapters. ``subscribe`` picks the default; the webhook routes
# carry the provider in the path. Paymob is the only provider.
_GATEWAYS: dict[str, type[PaymentGateway]] = {
    "paymob": PaymobGateway,
}

DEFAULT_PROVIDER = "paymob"


def get_gateway(provider: str = DEFAULT_PROVIDER) -> PaymentGateway:
    """Return a configured gateway adapter for ``provider``.

    Raises ``ValueError`` for an unknown provider so callers fail loudly rather
    than silently routing money to the wrong place.
    """
    try:
        return _GATEWAYS[provider]()
    except KeyError as exc:
        raise ValueError(f"Unknown payment provider: {provider!r}") from exc


__all__ = [
    "DEFAULT_PROVIDER",
    "PaymentGateway",
    "PaymobGateway",
    "WebhookEvent",
    "get_gateway",
]
