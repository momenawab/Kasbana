"""Enrollment models — referral tracking.

The join flow itself writes to ``core`` (CustomerCard + ledger). This model
records who referred whom so a referral converts at most once and the reporting
is auditable. Bonus stamps are granted via ``core.ledger.grant_stamps``.
"""

from __future__ import annotations

from django.db import models

from core.models import Card, CustomerCard, Merchant, TimeStampedModel, UUIDModel


class Referral(UUIDModel, TimeStampedModel):
    """One converted referral: ``referrer`` invited ``referee`` to ``card``.

    ``referee`` is unique — a customer can be referred only once — which also
    makes the grant idempotent under a concurrent double-submit.
    """

    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="referrals")
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="referrals")
    referrer = models.ForeignKey(
        CustomerCard, on_delete=models.CASCADE, related_name="referrals_made"
    )
    referee = models.OneToOneField(
        CustomerCard, on_delete=models.CASCADE, related_name="referral_source"
    )

    class Meta:
        indexes = [models.Index(fields=["merchant", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.referrer_id} → {self.referee_id}"
