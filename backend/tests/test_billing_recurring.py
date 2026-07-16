"""Recurring-subscription model + catalogue semantics (Paymob plan, phase 1).

Covers what the card-upfront trial changes about *access*: the PENDING_CARD
gate, trialing on the tier the merchant picked (rather than a fixed Growth),
and the annual side of the price ladder. The Paymob round-trips themselves land
with the adapter rewrite; nothing here touches the network.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from billing import entitlements, services
from billing.models import Plan
from billing.plans import (
    INTERVAL_DAYS,
    PAYMOB_FREQUENCIES,
    PLAN_PRICES_EGP,
    PLAN_PRICES_EGP_ANNUAL,
    TRIAL_PLAN,
    BillingInterval,
    BillingStatus,
    invalidate_plan_cache,
    plan_price,
)
from billing.wire import status_to_wire
from core.enums import PlanTier

pytestmark = pytest.mark.django_db


# ── PENDING_CARD: signed up, no card yet ────────────────────────────────────
def test_pending_card_is_locked(merchant):
    """No card ⇒ no dashboard: the trial clock hasn't started, so nothing is
    entitled even though a plan may already be picked."""
    sub = services.subscription_for(merchant)
    sub.status = BillingStatus.PENDING_CARD
    sub.plan = PlanTier.GROWTH
    sub.save()

    assert sub.effective_plan() is None
    assert sub.trial_active() is False
    assert entitlements.check(merchant, "export") is False


def test_pending_card_reports_suspended_on_the_wire(merchant):
    """The contract has no pre-trial value; PENDING_CARD must not leak as
    "active" (the fall-through), since access is in fact locked."""
    sub = services.subscription_for(merchant)
    sub.status = BillingStatus.PENDING_CARD
    sub.save()
    assert status_to_wire(merchant, sub) == "suspended"


def test_admin_override_still_reaches_a_carded_out_merchant(merchant):
    """Support must be able to unblock someone stuck at the gate — the override
    outranks PENDING_CARD like it outranks a lock."""
    sub = services.subscription_for(merchant)
    sub.status = BillingStatus.PENDING_CARD
    sub.override_plan = PlanTier.STARTER
    sub.save()
    assert sub.effective_plan() == PlanTier.STARTER


# ── Trial runs on the plan the merchant picked ──────────────────────────────
def test_trial_runs_on_the_selected_plan(merchant):
    """Post-gate signups trial on their chosen tier, not a fixed Growth — a
    Starter trialist must not get Growth's limits."""
    sub = services.subscription_for(merchant)
    sub.plan = PlanTier.STARTER
    sub.trial_started_at = timezone.now()
    sub.card_verified = True
    sub.save()

    assert sub.effective_plan() == PlanTier.STARTER
    # Growth-only features stay off for a Starter trialist.
    assert entitlements.check(merchant, "specialized_roles") is False


def test_legacy_card_free_trial_still_gets_growth(merchant):
    """Rows that started a trial before a plan was ever picked (plan == FREE)
    keep the old fixed Growth-level trial rather than dropping to FREE limits."""
    sub = services.subscription_for(merchant)
    assert sub.plan == PlanTier.FREE  # never went through the gate
    assert sub.effective_plan() == TRIAL_PLAN == PlanTier.GROWTH
    assert entitlements.check(merchant, "specialized_roles") is True


def test_expired_trial_locks_regardless_of_selected_plan(merchant):
    sub = services.subscription_for(merchant)
    sub.plan = PlanTier.CHAIN
    sub.trial_ends_at = timezone.now() - timedelta(days=1)
    sub.save()
    assert sub.effective_plan() is None


# ── Annual pricing ──────────────────────────────────────────────────────────
def test_annual_price_is_ten_months_of_monthly():
    """The "2 months free" framing on the pricing page has to be what checkout
    actually charges."""
    for tier in (PlanTier.STARTER, PlanTier.GROWTH, PlanTier.CHAIN):
        assert PLAN_PRICES_EGP_ANNUAL[tier] == PLAN_PRICES_EGP[tier] * 10


def test_plan_price_defaults_to_monthly():
    """Existing callers (MRR, coupon discounts) pass no interval and must keep
    meaning monthly."""
    assert plan_price(PlanTier.GROWTH) == plan_price(PlanTier.GROWTH, BillingInterval.MONTHLY)
    assert plan_price(PlanTier.GROWTH) == Decimal("999")


def test_plan_price_reads_the_annual_column():
    """The seed migration backfills price_egp_annual; a 0 here would mean an
    annual subscriber is charged nothing."""
    invalidate_plan_cache()
    assert plan_price(PlanTier.GROWTH, BillingInterval.ANNUAL) == Decimal("9990")
    assert plan_price(PlanTier.STARTER, BillingInterval.ANNUAL) == Decimal("5990")


def test_admin_edit_to_the_annual_price_reaches_checkout():
    """Annual pricing is admin-editable like the monthly ladder (Phase 3)."""
    Plan.objects.filter(key=PlanTier.STARTER).update(price_egp_annual=Decimal("4990"))
    invalidate_plan_cache()
    assert plan_price(PlanTier.STARTER, BillingInterval.ANNUAL) == Decimal("4990")
    # ...and doesn't disturb the monthly price.
    assert plan_price(PlanTier.STARTER) == Decimal("599")


# ── Paymob plan mapping ─────────────────────────────────────────────────────
def test_paymob_plan_id_resolves_per_interval():
    plan = Plan.objects.get(key=PlanTier.GROWTH)
    plan.paymob_plan_id_monthly = "pm-123"
    plan.paymob_plan_id_annual = "pm-456"
    plan.save()

    assert plan.paymob_plan_id(BillingInterval.MONTHLY) == "pm-123"
    assert plan.paymob_plan_id(BillingInterval.ANNUAL) == "pm-456"


def test_paymob_plan_id_is_blank_until_ops_maps_it():
    """Unmapped is the shipped state until `create_paymob_plans` runs per env —
    it must read as empty, not raise."""
    assert Plan.objects.get(key=PlanTier.CHAIN).paymob_plan_id(BillingInterval.MONTHLY) == ""


def test_subscription_defaults_to_monthly(merchant):
    assert services.subscription_for(merchant).billing_interval == BillingInterval.MONTHLY


def test_every_interval_maps_to_a_frequency_paymob_accepts():
    """Paymob's `frequency` is a closed enum (7/15/30/60/90/180/360); a value
    outside it fails plan creation with 400 "is not a valid choice", which we'd
    only discover against the live API."""
    assert set(INTERVAL_DAYS) == set(BillingInterval.values)
    for interval, days in INTERVAL_DAYS.items():
        assert days in PAYMOB_FREQUENCIES, f"{interval} -> {days} is not a Paymob frequency"
