"""Coupon validation, discount math + redemption (Phase 11).

Server-side is the only place caps are trusted: ``validate`` checks
active/expiry/plan-scope/global-cap/per-merchant, and ``redeem`` re-checks the
global cap under a row lock before recording, so concurrent redemptions can't
overshoot ``max_redemptions``.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from billing.models import Coupon, CouponRedemption
from core.models import Merchant


class CouponError(Exception):
    """Coupon can't be applied. ``code`` is a stable machine code for the API."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def normalize(code: str) -> str:
    return (code or "").strip().upper()


def get_active(code: str) -> Coupon | None:
    return Coupon.objects.filter(code=normalize(code)).first()


def validate(coupon: Coupon, merchant: Merchant, plan: str | None = None) -> None:
    """Raise ``CouponError`` if ``coupon`` can't be redeemed by ``merchant``."""
    if not coupon.active:
        raise CouponError("COUPON_INACTIVE", "This code is no longer active.")
    if coupon.expires_at is not None and coupon.expires_at <= timezone.now():
        raise CouponError("COUPON_EXPIRED", "This code has expired.")
    if plan and coupon.plan_scope and plan not in coupon.plan_scope:
        raise CouponError("COUPON_PLAN_SCOPE", "This code isn't valid for that plan.")
    if coupon.max_redemptions is not None and coupon.redemption_count >= coupon.max_redemptions:
        raise CouponError("COUPON_EXHAUSTED", "This code has reached its redemption limit.")
    if (
        coupon.per_merchant_once
        and CouponRedemption.objects.filter(coupon=coupon, merchant=merchant).exists()
    ):
        raise CouponError("COUPON_ALREADY_USED", "This merchant has already used this code.")


def discounted_amount(coupon: Coupon, amount: Decimal) -> Decimal:
    """The charge after applying a percent/fixed coupon (never below 0)."""
    if coupon.type == Coupon.Type.PERCENT:
        discounted = amount * (Decimal("100") - coupon.value) / Decimal("100")
    elif coupon.type == Coupon.Type.FIXED:
        discounted = amount - coupon.value
    else:
        discounted = amount  # non-checkout types don't change the charge
    return max(Decimal("0"), discounted.quantize(Decimal("0.01")))


@transaction.atomic
def redeem(
    coupon: Coupon, merchant: Merchant, *, discount_egp: Decimal, detail: str = ""
) -> CouponRedemption:
    """Record a redemption, re-checking the global cap under a row lock."""
    locked = Coupon.objects.select_for_update().get(pk=coupon.pk)
    if locked.max_redemptions is not None and locked.redemption_count >= locked.max_redemptions:
        raise CouponError("COUPON_EXHAUSTED", "This code has reached its redemption limit.")
    if (
        locked.per_merchant_once
        and CouponRedemption.objects.filter(coupon=locked, merchant=merchant).exists()
    ):
        raise CouponError("COUPON_ALREADY_USED", "This merchant has already used this code.")
    redemption = CouponRedemption.objects.create(
        coupon=locked, merchant=merchant, discount_egp=discount_egp, detail=detail
    )
    locked.redemption_count += 1
    locked.save(update_fields=["redemption_count"])
    return redemption
