"""Referral conversion — grant bonus stamps to referrer + referee.

Called from the enroll flow when a new customer joins via ``?ref=<referrer id>``.
Best-effort and heavily guarded: a referral converts at most once, never rewards
a self-referral, and only counts a referrer who is an active holder of the card.
"""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction

from core import constants, ledger
from core.enums import CustomerCardStatus
from core.models import Card, CustomerCard
from enrollment.models import Referral

logger = logging.getLogger(__name__)


def apply_referral(card: Card, referee: CustomerCard, ref_id: str | None) -> Referral | None:
    """Record the referral + grant bonus stamps to both parties, or return None.

    No-op when: referrals are off for the card, no/blank ``ref_id``, the referrer
    isn't an active holder of this card, it's a self-referral, or the referee was
    already referred (unique constraint).
    """
    if not card.referral_enabled or not ref_id:
        return None

    referrer = (
        CustomerCard.objects.filter(card=card, id=ref_id, status=CustomerCardStatus.ACTIVE)
        .exclude(id=referee.id)
        .first()
    )
    if referrer is None:
        return None

    try:
        with transaction.atomic():
            referral = Referral.objects.create(
                card=card, merchant=card.merchant, referrer=referrer, referee=referee
            )
    except IntegrityError:
        return None  # referee already has a referral source

    bonus = constants.REFERRAL_BONUS_STAMPS
    ledger.grant_stamps(referrer, delta=bonus, note="Referral bonus")
    ledger.grant_stamps(referee, delta=bonus, note="Welcome referral bonus")
    logger.info("Referral converted: %s → %s (card %s)", referrer.id, referee.id, card.id)
    return referral
