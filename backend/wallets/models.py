"""Wallet models — the per-card message ledger for free wallet push.

The wallet backends are otherwise stateless (they build passes on demand). This
one model persists the *latest message* shown on a customer's pass so the Apple
pass builder can render it as a back field with a ``changeMessage`` (which is
what makes iOS surface a lock-screen notification when it changes). Google reads
nothing from here — its ``addMessage`` API stores the message on Google's side —
but we record every send for both platforms for history/debugging.
"""

from __future__ import annotations

from django.db import models

from core.models import CustomerCard, TimeStampedModel, UUIDModel


class WalletMessage(UUIDModel, TimeStampedModel):
    """A push message sent to one customer's wallet pass (free channel).

    The newest row for a ``customer_card`` is the one the Apple pass surfaces;
    older rows are kept only as a sent-history trail.
    """

    customer_card = models.ForeignKey(
        CustomerCard, on_delete=models.CASCADE, related_name="wallet_messages"
    )
    title = models.CharField(max_length=120, blank=True)
    body = models.TextField()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["customer_card", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.customer_card_id}: {self.body[:32]}"
