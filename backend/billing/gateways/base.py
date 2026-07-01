"""``PaymentGateway`` interface + the provider-agnostic webhook event.

Both adapters translate their provider's payload into a ``WebhookEvent`` so the
billing service layer never branches on the provider: a verified ``success``
event activates the plan, a ``failed``/``canceled`` event locks the merchant.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True)
class CheckoutSession:
    """The result of creating a hosted checkout — what ``subscribe`` returns."""

    checkout_url: str
    gateway_ref: str


@dataclass(frozen=True)
class WebhookEvent:
    """Normalised gateway event the billing service acts on.

    ``kind`` is one of ``success`` / ``failed`` / ``canceled`` / ``ignored``.
    ``merchant_id`` and ``plan`` are echoed back from the checkout metadata we
    sent at creation time; ``amount_egp`` drives the ``Invoice`` row.
    """

    provider: str
    kind: str
    gateway_ref: str
    merchant_id: str | None = None
    plan: str | None = None
    amount_egp: Decimal | None = None


class PaymentGateway(Protocol):
    """The seam billing calls; Paymob/Fawry implement it (contract §3.10)."""

    provider: str

    def create_checkout(
        self, *, merchant_id: str, plan: str, amount_egp: Decimal, customer_email: str = ""
    ) -> CheckoutSession:
        """Create a hosted-checkout session and return its URL + gateway ref."""
        ...

    def verify_and_parse(self, *, headers: dict[str, str], body: bytes) -> WebhookEvent:
        """Verify the webhook signature, then parse it into a ``WebhookEvent``.

        Raises ``WebhookVerificationError`` when the signature does not match,
        so the view can return 400 without touching subscription state.
        """
        ...


class WebhookVerificationError(Exception):
    """Raised when a webhook signature fails verification."""


def _to_egp(value: Any) -> Decimal:
    """Coerce a provider amount (string/number) to an EGP ``Decimal``."""
    return Decimal(str(value))
