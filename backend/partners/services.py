"""Partner referral domain logic (Phase E.1).

Attribution (signup code / admin) and the one-time comp-months grant that fires
when a referred merchant first converts to paid. Everything here is best-effort
from the caller's point of view: a referral or reward failure must never break
signup or a payment webhook (the callers wrap accordingly).
"""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import Merchant
from partners.models import Partner, PartnerProgramConfig, PartnerReferral

logger = logging.getLogger(__name__)


def resolve_partner(code: str) -> Partner | None:
    """An active partner for ``code`` (case-insensitive), or ``None``."""
    code = (code or "").strip()
    if not code:
        return None
    return Partner.objects.filter(code__iexact=code, active=True).first()


def _attribute(partner: Partner, merchant: Merchant, source: str) -> PartnerReferral | None:
    """Create a referral, guarding self-referral and already-referred merchants."""
    if partner.merchant_id == merchant.id:
        return None  # a merchant can't refer itself
    if PartnerReferral.objects.filter(referred_merchant=merchant).exists():
        return None  # referred by at most one partner; first attribution wins
    try:
        return PartnerReferral.objects.create(
            partner=partner, referred_merchant=merchant, attributed_via=source
        )
    except IntegrityError:
        return None  # raced another attribution — leave the first in place


def attribute_signup(merchant: Merchant, code: str) -> PartnerReferral | None:
    """Attribute a freshly-signed-up ``merchant`` to the partner behind ``code``.

    Best-effort: an unknown/blank code or any failure simply yields ``None`` and
    signup proceeds unaffected.
    """
    partner = resolve_partner(code)
    if partner is None:
        return None
    return _attribute(partner, merchant, PartnerReferral.Source.SIGNUP_CODE)


def assign_admin(partner: Partner, merchant: Merchant) -> PartnerReferral | None:
    """Manually attribute ``merchant`` to ``partner`` (admin action)."""
    return _attribute(partner, merchant, PartnerReferral.Source.ADMIN)


@transaction.atomic
def on_merchant_converted(merchant: Merchant) -> None:
    """Fire the one-time referral reward when ``merchant`` first converts to paid.

    No-op unless the merchant was referred, the reward hasn't been granted yet,
    and the program (per the partner's resolved config) is enabled. Grants both
    the partner and the new merchant their configured free months. Import of
    ``billing`` is deferred to avoid a billing↔partners import cycle.
    """
    referral = (
        PartnerReferral.objects.select_for_update()
        .filter(referred_merchant=merchant, reward_granted=False)
        .select_related("partner")
        .first()
    )
    if referral is None:
        return

    cfg = referral.partner.resolved_config()
    if not cfg.enabled:
        return

    from billing import services as billing

    if cfg.merchant_free_months > 0:
        billing.grant_free_months(merchant, cfg.merchant_free_months)
    if cfg.partner_free_months > 0:
        billing.grant_free_months(referral.partner.merchant, cfg.partner_free_months)

    referral.converted_at = timezone.now()
    referral.reward_granted = True
    referral.merchant_months_granted = cfg.merchant_free_months
    referral.partner_months_granted = cfg.partner_free_months
    referral.save(
        update_fields=[
            "converted_at",
            "reward_granted",
            "merchant_months_granted",
            "partner_months_granted",
            "updated_at",
        ]
    )
    logger.info(
        "partner_reward_granted",
        extra={
            "partner_id": str(referral.partner_id),
            "referred_merchant_id": str(merchant.id),
            "partner_months": cfg.partner_free_months,
            "merchant_months": cfg.merchant_free_months,
        },
    )


def program_config() -> PartnerProgramConfig:
    """The global program config row (created with defaults on first access)."""
    return PartnerProgramConfig.get_solo()
