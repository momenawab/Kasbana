"""core/ledger.py — THE ONLY way to change a balance (contract §3.5).

No endpoint writes to ``StampLedger`` or ``CustomerCard.stamp_count`` directly;
every mutation flows through here so the two phases stay consistent. All
mutations are atomic and lock the customer card row to avoid lost updates.

Anti-fraud (contract §3.3) is enforced inside ``add_stamp``: per-card cooldown,
per-card daily cap, and per-staff per-minute cap. Violations raise the domain
exceptions in ``common/errors.py`` which map to the frozen error codes.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from common.errors import CooldownActive, RateLimited, RewardNotReady
from core import constants
from core.enums import CustomerCardStatus, LedgerEvent, RedemptionStatus
from core.models import CustomerCard, Redemption, Reward, StaffUser, StampLedger


def current_balance(customer_card: CustomerCard) -> int:
    """Authoritative balance = sum of all ledger deltas for the card.

    The cached ``CustomerCard.stamp_count`` is kept in step with this value by
    every mutation below; this function recomputes from the append-only ledger.
    """
    total = (
        StampLedger.objects.filter(customer_card=customer_card)
        .aggregate(total=_sum("delta"))
        .get("total")
    )
    return int(total or 0)


def is_reward_ready(customer_card: CustomerCard) -> bool:
    """True once the card's balance reaches the program's ``stamps_required``."""
    required = customer_card.card.stamps_required
    return required > 0 and customer_card.stamp_count >= required


def is_one_from_reward(customer_card: CustomerCard) -> bool:
    """True when the card is exactly one stamp short of the reward threshold."""
    required = customer_card.card.stamps_required
    return required > 0 and customer_card.stamp_count == required - 1


def record_enrollment(customer_card: CustomerCard) -> StampLedger:
    """Append the opening ENROLL event (delta 0) for a freshly enrolled card."""
    with transaction.atomic():
        card = _lock(customer_card)
        return _append(
            card,
            event_type=LedgerEvent.ENROLL,
            delta=0,
            balance_after=card.stamp_count,
        )


def add_stamp(
    customer_card: CustomerCard,
    *,
    staff: StaffUser | None = None,
    location: object | None = None,
    delta: int = 1,
    note: str = "",
    force: bool = False,
    skip_guards: bool = False,
) -> StampLedger:
    """Append a STAMP event, update cached ``stamp_count``, return the row.

    Raises CooldownActive / RateLimited (contract §3.3 / §3.7). ``force`` skips
    only the soft per-card cooldown (cashier-confirmed repeat stamp); the daily
    and per-staff rate limits still apply.

    ``skip_guards`` drops the anti-fraud guards entirely and is **only** for
    demo/test cards (``console.demo_cards``), which have no reward economics to
    protect: a rep stamping a pass live in a proposal would otherwise trip the
    30-second cooldown and the 12-per-day cap mid-pitch. Never pass it on a real
    merchant's card — the caller, not this function, owns that check.
    """
    with transaction.atomic():
        card = _lock(customer_card)
        if not skip_guards:
            _enforce_stamp_guards(card, staff, force=force)

        new_balance = card.stamp_count + delta
        entry = _append(
            card,
            event_type=LedgerEvent.STAMP,
            delta=delta,
            balance_after=new_balance,
            staff=staff,
            location=location,
            note=note,
        )
        _apply_balance(card, new_balance)
        return entry


def redeem_reward(
    customer_card: CustomerCard,
    reward: Reward,
    *,
    staff: StaffUser | None = None,
    location: object | None = None,
) -> Redemption:
    """Append a REDEEM event and create a Redemption. Raises RewardNotReady."""
    with transaction.atomic():
        card = _lock(customer_card)

        threshold = reward.threshold
        if card.stamp_count < threshold:
            raise RewardNotReady()

        new_balance = card.stamp_count - threshold
        _append(
            card,
            event_type=LedgerEvent.REDEEM,
            delta=-threshold,
            balance_after=new_balance,
            staff=staff,
            location=location,
            note=f"Redeemed: {reward.title}",
        )
        _apply_balance(card, new_balance)

        # Single-use programs complete on redeem — the pass is expired/voided by
        # the wallet builders once the card is no longer ACTIVE.
        if card.card.single_use and card.status != CustomerCardStatus.COMPLETED:
            card.status = CustomerCardStatus.COMPLETED
            card.save(update_fields=["status", "updated_at"])

        return Redemption.objects.create(
            customer_card=card,
            reward=reward,
            merchant=card.merchant,
            staff=staff,
            location=location,
            status=RedemptionStatus.CLAIMED,
        )


def grant_stamps(customer_card: CustomerCard, *, delta: int = 1, note: str = "") -> StampLedger:
    """Grant bonus stamps *without* the anti-fraud guards — for system rewards
    like referrals, never for staff scans (use ``add_stamp`` for those)."""
    with transaction.atomic():
        card = _lock(customer_card)
        new_balance = card.stamp_count + delta
        entry = _append(
            card, event_type=LedgerEvent.STAMP, delta=delta, balance_after=new_balance, note=note
        )
        _apply_balance(card, new_balance)
        return entry


# ── internals ─────────────────────────────────────────────────────────────────
def _sum(field: str):
    from django.db.models import Sum

    return Sum(field)


def _lock(customer_card: CustomerCard) -> CustomerCard:
    """Re-fetch the card row with a row lock for the duration of the txn."""
    return CustomerCard.objects.select_for_update().get(pk=customer_card.pk)


def _append(
    customer_card: CustomerCard,
    *,
    event_type: str,
    delta: int,
    balance_after: int,
    staff: StaffUser | None = None,
    location: object | None = None,
    note: str = "",
) -> StampLedger:
    return StampLedger.objects.create(
        customer_card=customer_card,
        merchant=customer_card.merchant,
        event_type=event_type,
        delta=delta,
        balance_after=balance_after,
        staff=staff,
        location=location,
        note=note,
    )


def _apply_balance(customer_card: CustomerCard, new_balance: int) -> None:
    customer_card.stamp_count = new_balance
    customer_card.last_event_at = timezone.now()
    customer_card.save(update_fields=["stamp_count", "last_event_at", "updated_at"])


def _enforce_stamp_guards(
    customer_card: CustomerCard, staff: StaffUser | None, force: bool = False
) -> None:
    now = timezone.now()

    # The per-card cooldown is a *soft* guard: the till surfaces it as a confirm
    # ("you stamped this recently — again?") and re-sends with ``force`` when the
    # cashier confirms, so a legitimate repeat stamp isn't blocked. The daily and
    # per-staff limits below stay hard anti-fraud and are never forced.
    if not force:
        last_stamp = (
            StampLedger.objects.filter(customer_card=customer_card, event_type=LedgerEvent.STAMP)
            .order_by("-created_at")
            .first()
        )
        if last_stamp is not None:
            elapsed = (now - last_stamp.created_at).total_seconds()
            if elapsed < constants.STAMP_COOLDOWN_SECONDS:
                raise CooldownActive()

    today_count = StampLedger.objects.filter(
        customer_card=customer_card,
        event_type=LedgerEvent.STAMP,
        created_at__date=timezone.localdate(now),
    ).count()
    if today_count >= constants.MAX_STAMPS_PER_CARD_PER_DAY:
        raise RateLimited("Daily stamp limit reached for this card.")

    if staff is not None:
        minute_ago = now - timedelta(minutes=1)
        staff_count = StampLedger.objects.filter(
            staff=staff,
            event_type=LedgerEvent.STAMP,
            created_at__gte=minute_ago,
        ).count()
        if staff_count >= constants.MAX_STAMPS_PER_STAFF_PER_MIN:
            raise RateLimited("Staff stamp rate limit exceeded.")
