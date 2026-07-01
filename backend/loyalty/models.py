"""Loyalty models — idempotency ledger for mutating endpoints.

The loyalty engine itself writes only to ``core`` (``StampLedger``/``CustomerCard``
via ``core.ledger``). The single model here is operational: it lets ``stamp`` and
``redeem`` be retried safely (a dropped response → client retry must not issue a
second stamp).
"""

from __future__ import annotations

from django.db import models

from core.models import Merchant


class IdempotencyRecord(models.Model):
    """Stored result of a mutating loyalty request, keyed by a client-supplied
    ``Idempotency-Key`` header (scoped to merchant + endpoint).

    A request first *claims* the key (``response`` null), runs the mutation, then
    stores its response. A replay with the same key returns that stored response
    instead of repeating the mutation; a concurrent duplicate that arrives while
    the first is still in flight (``response`` still null) gets a 409.
    """

    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="idempotency_records"
    )
    endpoint = models.CharField(max_length=32)  # "stamp" | "redeem"
    key = models.CharField(max_length=128)
    response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "endpoint", "key"],
                name="uniq_idem_merchant_endpoint_key",
            )
        ]
        # created_at index supports a future periodic purge of old keys.
        indexes = [models.Index(fields=["created_at"])]

    def __str__(self) -> str:
        return f"{self.merchant_id} · {self.endpoint} · {self.key}"
