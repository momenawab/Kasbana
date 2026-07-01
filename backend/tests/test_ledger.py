"""Tests for core/ledger.py — the highest-risk logic (contract DoD §6)."""

from __future__ import annotations

import pytest

from common.errors import CooldownActive, RateLimited, RewardNotReady
from core import constants, ledger
from core.enums import LedgerEvent, RedemptionStatus
from core.models import Redemption, StampLedger
from tests import factories

pytestmark = pytest.mark.django_db


def test_record_enrollment_appends_zero_delta(customer_card):
    entry = ledger.record_enrollment(customer_card)
    assert entry.event_type == LedgerEvent.ENROLL
    assert entry.delta == 0
    assert entry.balance_after == 0


def test_add_stamp_updates_cache_and_ledger(customer_card, no_cooldown):
    ledger.add_stamp(customer_card)
    customer_card.refresh_from_db()
    assert customer_card.stamp_count == 1
    assert customer_card.last_event_at is not None
    assert ledger.current_balance(customer_card) == 1


def test_balance_math_across_multiple_stamps(customer_card, no_cooldown):
    for _ in range(5):
        ledger.add_stamp(customer_card)
    customer_card.refresh_from_db()
    assert customer_card.stamp_count == 5
    assert ledger.current_balance(customer_card) == 5
    assert ledger.is_reward_ready(customer_card) is True


def test_cooldown_blocks_rapid_stamp(customer_card, monkeypatch):
    monkeypatch.setattr(constants, "STAMP_COOLDOWN_SECONDS", 30)
    ledger.add_stamp(customer_card)
    with pytest.raises(CooldownActive):
        ledger.add_stamp(customer_card)


def test_daily_cap_raises_rate_limited(customer_card, no_cooldown, monkeypatch):
    monkeypatch.setattr(constants, "MAX_STAMPS_PER_CARD_PER_DAY", 3)
    for _ in range(3):
        ledger.add_stamp(customer_card)
    with pytest.raises(RateLimited):
        ledger.add_stamp(customer_card)


def test_staff_per_minute_cap(customer_card, no_cooldown, monkeypatch):
    monkeypatch.setattr(constants, "MAX_STAMPS_PER_STAFF_PER_MIN", 2)
    staff = factories.StaffUserFactory(merchant=customer_card.merchant)
    for _ in range(2):
        ledger.add_stamp(customer_card, staff=staff)
    with pytest.raises(RateLimited):
        ledger.add_stamp(customer_card, staff=staff)


def test_redeem_reduces_balance_and_creates_redemption(customer_card, reward, no_cooldown):
    for _ in range(5):
        ledger.add_stamp(customer_card)
    redemption = ledger.redeem_reward(customer_card, reward)
    customer_card.refresh_from_db()
    assert isinstance(redemption, Redemption)
    assert redemption.status == RedemptionStatus.CLAIMED
    assert customer_card.stamp_count == 0
    assert ledger.current_balance(customer_card) == 0


def test_redeem_below_threshold_raises(customer_card, reward):
    with pytest.raises(RewardNotReady):
        ledger.redeem_reward(customer_card, reward)


def test_single_use_card_completes_on_redeem(customer_card, reward, no_cooldown):
    from core.enums import CustomerCardStatus

    customer_card.card.single_use = True
    customer_card.card.save(update_fields=["single_use"])
    for _ in range(5):
        ledger.add_stamp(customer_card)

    ledger.redeem_reward(customer_card, reward)
    customer_card.refresh_from_db()
    assert customer_card.status == CustomerCardStatus.COMPLETED


def test_reusable_card_stays_active_on_redeem(customer_card, reward, no_cooldown):
    from core.enums import CustomerCardStatus

    assert customer_card.card.single_use is False  # default
    for _ in range(5):
        ledger.add_stamp(customer_card)

    ledger.redeem_reward(customer_card, reward)
    customer_card.refresh_from_db()
    assert customer_card.status == CustomerCardStatus.ACTIVE


def test_ledger_is_append_only_trail(customer_card, reward, no_cooldown):
    ledger.record_enrollment(customer_card)
    for _ in range(5):
        ledger.add_stamp(customer_card)
    ledger.redeem_reward(customer_card, reward)
    trail = list(
        StampLedger.objects.filter(customer_card=customer_card)
        .order_by("created_at")
        .values_list("event_type", "delta", "balance_after")
    )
    assert trail == [
        ("ENROLL", 0, 0),
        ("STAMP", 1, 1),
        ("STAMP", 1, 2),
        ("STAMP", 1, 3),
        ("STAMP", 1, 4),
        ("STAMP", 1, 5),
        ("REDEEM", -5, 0),
    ]
