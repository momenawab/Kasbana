"""Enrollment models — referral tracking + the merchant's main join link.

The join flow itself writes to ``core`` (CustomerCard + ledger). ``Referral``
records who referred whom so a referral converts at most once and the reporting
is auditable. Bonus stamps are granted via ``core.ledger.grant_stamps``.

``MerchantEnrollLink`` lives here rather than on ``core.EnrollmentToken`` because
``core`` is frozen: it cannot gain a column. See ``enrollment.tokens``.
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


class MerchantEnrollLink(UUIDModel, TimeStampedModel):
    """The merchant's permanent join QR, pointing at whichever card is "main".

    A ``core.EnrollmentToken`` is bound to one Card, so re-pointing a printed QR
    at a different program is impossible: the token changes, the poster is dead.
    This row separates the two — the token is stable, ``primary_card`` moves. The
    merchant prints once and switches programs whenever they like.

    ``primary_card`` is ``SET_NULL`` so deleting the elected card leaves the link
    intact (it then 404s until a new card is elected, rather than guessing one).
    """

    merchant = models.OneToOneField(Merchant, on_delete=models.CASCADE, related_name="enroll_link")
    token = models.CharField(max_length=32, unique=True, db_index=True)
    primary_card = models.ForeignKey(
        Card, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"main-qr({self.merchant_id} → {self.primary_card_id})"
