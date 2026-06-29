"""Payment gateway adapters (Phase 1.7).

A thin ``PaymentGateway`` interface with Paymob/Fawry implementations. The
adapters own two concerns: creating a hosted-checkout URL for ``subscribe`` and
verifying + parsing the provider's webhook into a provider-agnostic
``WebhookEvent``. Network calls go through ``httpx``; in tests the adapters are
faked (no real HTTP) — see ``tests/test_billing_http.py``.

Real credentials are wired on staging (``PAYMOB_API_KEY``, ``FAWRY_*``); locally
the gateways run in a deterministic stub mode when their keys are unset.
"""

from __future__ import annotations

from billing.gateways.base import PaymentGateway, WebhookEvent
from billing.gateways.fawry import FawryGateway
from billing.gateways.paymob import PaymobGateway

# Provider key -> adapter. ``subscribe`` picks the default provider; the webhook
# routes carry the provider in the path.
_GATEWAYS: dict[str, type[PaymentGateway]] = {
    "paymob": PaymobGateway,
    "fawry": FawryGateway,
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
    "FawryGateway",
    "PaymentGateway",
    "PaymobGateway",
    "WebhookEvent",
    "get_gateway",
]
