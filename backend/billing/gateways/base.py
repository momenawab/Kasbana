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
    # The provider's *transaction* id (distinct from ``gateway_ref``, the order).
    # For a subscription-linking charge this is what later subscription
    # callbacks echo as ``initial_transaction`` — the only way to tie them back
    # to a merchant.
    transaction_ref: str = ""


@dataclass(frozen=True)
class SubscriptionEvent:
    """A verified Paymob *subscription*-lifecycle callback.

    Deliberately separate from ``WebhookEvent``: that one describes a single
    charge (success/failed/canceled), while this describes what happened to the
    recurring subscription itself. The two callbacks differ in payload shape and
    in HMAC formula, and a renewal has to update the subscription's period — not
    just book an invoice — so collapsing them would lose the distinction.

    ``trigger_type`` is Paymob's verbatim value (e.g. ``"Successful
    Transaction"``, ``"suspended"``); mapping it to a state change is the
    service layer's job, and unknown values must be ignored rather than fail —
    Paymob can add to the catalogue without telling us.
    """

    provider: str
    trigger_type: str
    subscription_id: str
    plan_id: str = ""
    state: str = ""
    amount_egp: Decimal | None = None
    next_billing: str = ""
    initial_transaction: str = ""


class PaymentGateway(Protocol):
    """The seam billing calls; Paymob implements it (contract §3.10)."""

    provider: str

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
        """Create a hosted-checkout session and return its URL + gateway ref.

        With ``subscription_plan_id``, the charge also links a recurring
        subscription; ``subscription_start_date`` (``YYYY-MM-DD``) defers the
        first full deduction — together, the card-upfront trial.
        """
        ...

    def verify_and_parse(self, *, headers: dict[str, str], body: bytes) -> WebhookEvent:
        """Verify the webhook signature, then parse it into a ``WebhookEvent``.

        Raises ``WebhookVerificationError`` when the signature does not match,
        so the view can return 400 without touching subscription state.
        """
        ...

    # ── Recurring subscriptions ───────────────────────────────────────────────
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
        """Create a recurring plan and return the provider's plan id (ops only)."""
        ...

    def suspend_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Stop the next deduction, reversibly."""
        ...

    def resume_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Undo a suspend."""
        ...

    def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Close the subscription permanently."""
        ...

    def verify_and_parse_subscription_event(
        self, *, headers: dict[str, str], body: bytes
    ) -> SubscriptionEvent:
        """Verify + parse a subscription-lifecycle callback.

        Separate from ``verify_and_parse``: the payload shape and the signature
        scheme both differ, and only these events move the billing period.
        """
        ...


class WebhookVerificationError(Exception):
    """Raised when a webhook signature fails verification."""


def _to_egp(value: Any) -> Decimal:
    """Coerce a provider amount (string/number) to an EGP ``Decimal``."""
    return Decimal(str(value))
