"""Core Celery tasks (contract §3.9). Queue: ``default``."""

from __future__ import annotations

from celery import shared_task


@shared_task(name="core.tasks.recompute_balance")
def recompute_balance(customer_card_id: str) -> int:
    """Recompute a card's cached ``stamp_count`` from the append-only ledger.

    Self-healing safety net if the cached balance ever drifts from the ledger.
    Returns the recomputed balance.
    """
    from django.db import transaction

    from core import ledger
    from core.models import CustomerCard

    with transaction.atomic():
        card = CustomerCard.objects.select_for_update().get(pk=customer_card_id)
        balance = ledger.current_balance(card)
        if card.stamp_count != balance:
            card.stamp_count = balance
            card.save(update_fields=["stamp_count", "updated_at"])
    return balance
