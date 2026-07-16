"""Webhook-delivery logging + replay helpers (Phase 14).

The webhook view records every received delivery here; the ops console replays a
stored one. Both round-trip through ``payload_from_event`` / ``event_from_payload``
so the stored JSON is exactly what ``apply_webhook_event`` needs — no raw signed
body is kept.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.utils import timezone

from billing.gateways.base import SubscriptionEvent, WebhookEvent
from billing.models import WebhookDelivery

logger = logging.getLogger(__name__)


def payload_from_event(event: WebhookEvent) -> dict[str, Any]:
    """JSON-safe dict of a WebhookEvent (Decimal → str for the JSONField)."""
    return {
        "provider": event.provider,
        "kind": event.kind,
        "gateway_ref": event.gateway_ref,
        "merchant_id": event.merchant_id,
        "plan": event.plan,
        "amount_egp": str(event.amount_egp) if event.amount_egp is not None else None,
    }


def event_from_payload(payload: dict[str, Any]) -> WebhookEvent:
    """Rebuild a WebhookEvent from a stored payload (for replay)."""
    amount = payload.get("amount_egp")
    return WebhookEvent(
        provider=payload.get("provider", ""),
        kind=payload.get("kind", ""),
        gateway_ref=payload.get("gateway_ref", ""),
        merchant_id=payload.get("merchant_id"),
        plan=payload.get("plan"),
        amount_egp=Decimal(amount) if amount is not None else None,
    )


# Paymob's trigger_type -> the short ``kind`` vocabulary the delivery log
# already speaks (success/failed/canceled/ignored). "Successful Transaction"
# alone overflows the 24-char column, and a mid-word truncation reads as a bug
# in the ops console; the verbatim trigger is kept in ``payload`` regardless.
_SUB_KINDS = {
    "Successful Transaction": "sub:success",
    "Failed Transaction": "sub:failed",
    "Failed Overdue Transaction": "sub:overdue",
    "suspended": "sub:suspended",
    "canceled": "sub:canceled",
}


def record_subscription(
    provider: str,
    status: str,
    *,
    event: SubscriptionEvent | None = None,
    error: str = "",
) -> None:
    """Append a WebhookDelivery for a *subscription* callback. Never raises.

    ``gateway_ref`` holds the Paymob subscription id — the only id these
    callbacks carry.
    """
    try:
        payload: dict[str, Any] = {}
        if event is not None:
            payload = {
                "provider": event.provider,
                "trigger_type": event.trigger_type,
                "subscription_id": event.subscription_id,
                "plan_id": event.plan_id,
                "state": event.state,
                "amount_egp": str(event.amount_egp) if event.amount_egp is not None else None,
                "next_billing": event.next_billing,
                "initial_transaction": event.initial_transaction,
            }
        WebhookDelivery.objects.create(
            provider=provider,
            kind=_SUB_KINDS.get(event.trigger_type, "sub:ignored") if event else "",
            gateway_ref=event.subscription_id if event else "",
            status=status,
            payload=payload,
            error=error[:500],
            processed_at=timezone.now() if status == WebhookDelivery.Status.PROCESSED else None,
        )
    except Exception:  # pragma: no cover - defensive; recording must never 500 a webhook
        logger.exception("failed to record subscription delivery (%s/%s)", provider, status)


def record(
    provider: str,
    status: str,
    *,
    event: WebhookEvent | None = None,
    error: str = "",
) -> None:
    """Append a WebhookDelivery row. Never raises — a logging failure must not
    break the gateway ack path."""
    try:
        payload = payload_from_event(event) if event is not None else {}
        WebhookDelivery.objects.create(
            provider=provider,
            kind=event.kind if event else "",
            gateway_ref=event.gateway_ref if event else "",
            merchant_id_hint=(event.merchant_id or "") if event else "",
            status=status,
            payload=payload,
            error=error[:500],
            processed_at=timezone.now() if status == WebhookDelivery.Status.PROCESSED else None,
        )
    except Exception:  # pragma: no cover - defensive; recording must never 500 a webhook
        logger.exception("failed to record webhook delivery (%s/%s)", provider, status)
