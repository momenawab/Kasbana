"""Per-merchant activity timeline (Phase 6) — cross-sourced, read-only.

Merges the merchant's recent events from the sources that already exist —
loyalty ledger (enroll/stamp/redeem/adjust), invoices (billing), and admin
actions targeting the merchant — into one reverse-chronological feed. There is
no merchant-side login log today, so logins are absent until one exists.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

from billing.models import Invoice
from console.models import AdminAuditLog
from core.models import Merchant, StampLedger


class ActivityEvent(TypedDict):
    type: str
    at: datetime
    summary: str
    meta: dict[str, Any]


def timeline(merchant: Merchant, limit: int = 50) -> list[ActivityEvent]:
    events: list[ActivityEvent] = []

    ledger = (
        StampLedger.objects.filter(merchant=merchant)
        .select_related("customer_card", "staff__user", "location")
        .order_by("-created_at")[:limit]
    )
    for e in ledger:
        who = e.customer_card.customer_name or e.customer_card.customer_phone
        summary = f"{e.get_event_type_display()} · {who} ({e.delta:+d} → {e.balance_after})"
        events.append(
            {
                "type": e.event_type.lower(),  # enroll / stamp / redeem / adjust
                "at": e.created_at,
                "summary": summary,
                "meta": {
                    "customer": who,
                    "staff": e.staff.user.email if e.staff else "",
                    "location": e.location.name if e.location else "",
                },
            }
        )

    for inv in Invoice.objects.filter(merchant=merchant).order_by("-issued_at")[:limit]:
        events.append(
            {
                "type": f"invoice_{inv.status.lower()}",
                "at": inv.issued_at,
                "summary": f"Invoice {inv.status} · EGP {inv.amount_egp}",
                "meta": {"invoice_id": str(inv.id), "provider": inv.provider},
            }
        )

    admin_logs = AdminAuditLog.objects.filter(
        target_type__in=("merchant", "subscription"), target_id=str(merchant.id)
    ).order_by("-created_at")[:limit]
    for log in admin_logs:
        events.append(
            {
                "type": "admin_action",
                "at": log.created_at,
                "summary": f"{log.action} by {log.actor_email or 'admin'}",
                "meta": {"action": log.action, "reason": str(log.metadata.get("reason", ""))},
            }
        )

    events.sort(key=lambda ev: ev["at"], reverse=True)
    return events[:limit]
