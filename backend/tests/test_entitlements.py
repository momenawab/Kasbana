"""Tests for the billing entitlements engine + trial lifecycle (Phase 1.4).

Covers the plan-gating engine in isolation (``check``/``enforce`` across trial,
paid, and locked states; usage-counted limits vs feature flags), the trial
state machine on ``Subscription``, the ``expire_trials`` beat task, and the
dashboard gating that lights up now that the calls are wired (HTTP 402).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from billing import entitlements, services
from billing.models import Subscription
from billing.plans import PLAN_LIMITS, BillingStatus
from billing.tasks import expire_trials
from common.errors import PlanLimit
from core.enums import PlanTier
from tests import factories

pytestmark = pytest.mark.django_db


# ── Trial state ─────────────────────────────────────────────────────────────
def test_subscription_for_starts_a_trial(merchant):
    sub = services.subscription_for(merchant)
    assert sub.status == BillingStatus.TRIALING
    assert sub.trial_active()
    # Trial grants full Growth-level access regardless of stored plan.
    assert sub.effective_plan() == PlanTier.GROWTH


def test_subscription_for_is_idempotent(merchant):
    first = services.subscription_for(merchant)
    second = services.subscription_for(merchant)
    assert first.pk == second.pk
    assert Subscription.objects.filter(merchant=merchant).count() == 1


def test_trial_grants_growth_features(merchant):
    # Trial = Growth-level: export/specialized_roles/custom_branding/referral on.
    # API is no longer a ladder feature (bespoke Custom-only), so it stays off.
    assert entitlements.check(merchant, "export") is True
    assert entitlements.check(merchant, "api") is False
    assert entitlements.check(merchant, "specialized_roles") is True
    assert entitlements.check(merchant, "custom_branding") is True
    assert entitlements.check(merchant, "referral") is True


# ── Locked: expired trial / cancel ──────────────────────────────────────────
def test_expired_trial_locks_all_capabilities(merchant):
    sub = services.subscription_for(merchant)
    sub.trial_ends_at = timezone.now() - timedelta(days=1)
    sub.save()
    assert sub.effective_plan() is None
    assert entitlements.check(merchant, "max_cards") is False
    assert entitlements.check(merchant, "export") is False


def test_enforce_raises_plan_limit_when_locked(merchant):
    services.lock(merchant)
    with pytest.raises(PlanLimit):
        entitlements.enforce(merchant, "max_cards")


# ── Paid plans: counted limits + feature flags ──────────────────────────────
def test_active_free_plan_card_limit(merchant):
    services.activate_plan(merchant, PlanTier.FREE)
    assert PLAN_LIMITS[PlanTier.FREE]["max_cards"] == 1
    assert entitlements.check(merchant, "max_cards") is True  # 0 < 1
    factories.CardFactory(merchant=merchant)
    assert entitlements.check(merchant, "max_cards") is False  # 1 == 1, at cap


def test_activate_plan_mirrors_onto_merchant(merchant):
    services.activate_plan(merchant, PlanTier.STARTER, provider="paymob", gateway_ref="sub_1")
    merchant.refresh_from_db()
    assert merchant.plan == PlanTier.STARTER
    sub = Subscription.objects.get(merchant=merchant)
    assert sub.status == BillingStatus.ACTIVE
    assert sub.provider == "paymob"


def test_starter_plan_denies_api_feature(merchant):
    services.activate_plan(merchant, PlanTier.STARTER)
    assert entitlements.check(merchant, "api") is False
    assert entitlements.check(merchant, "export") is True


def test_chain_plan_has_unlimited_cards(merchant):
    services.activate_plan(merchant, PlanTier.CHAIN)
    for _ in range(15):
        factories.CardFactory(merchant=merchant)
    assert entitlements.check(merchant, "max_cards") is True


def test_unknown_capability_raises(merchant):
    with pytest.raises(ValueError):
        entitlements.check(merchant, "teleport")


# ── Beat task ────────────────────────────────────────────────────────────────
def test_expire_trials_locks_lapsed_subscriptions(merchant):
    sub = services.subscription_for(merchant)
    sub.trial_ends_at = timezone.now() - timedelta(hours=1)
    sub.save()
    assert expire_trials() == 1
    sub.refresh_from_db()
    assert sub.status == BillingStatus.LOCKED


def test_expire_trials_leaves_active_trials_alone(merchant):
    services.subscription_for(merchant)  # trial ends in 14 days
    assert expire_trials() == 0


# ── Dashboard integration: the wired gate returns 402 ────────────────────────
def test_create_card_over_plan_limit_returns_402(merchant):
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    services.activate_plan(merchant, PlanTier.FREE)  # max_cards = 1
    factories.CardFactory(merchant=merchant)  # already at the cap

    staff = factories.StaffUserFactory(merchant=merchant)
    client = APIClient()
    access = RefreshToken.for_user(staff.user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    resp = client.post(
        "/api/v1/cards",
        {"name": "Second", "stamps_required": 5, "reward_title": "x"},
        format="json",
    )
    assert resp.status_code == 402
    assert resp.json()["error"]["code"] == "PLAN_LIMIT"


def test_create_card_within_trial_succeeds(auth_client, merchant, monkeypatch):
    # Default merchant is on a trial -> Growth-level, so a first card is allowed.
    from wallets.tasks import sync_google_class

    monkeypatch.setattr(sync_google_class, "delay", lambda card_id: None)
    resp = auth_client.post(
        "/api/v1/cards",
        {"name": "First", "stamps_required": 5, "reward_title": "x"},
        format="json",
    )
    assert resp.status_code == 201


# ── Referral is a Growth+ feature; only enabling it is gated ─────────────────
def _card_client(merchant):
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    staff = factories.StaffUserFactory(merchant=merchant)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(staff.user).access_token}")
    return client


def test_referral_enable_denied_on_starter_returns_402(merchant):
    services.activate_plan(merchant, PlanTier.STARTER)  # referral off
    resp = _card_client(merchant).post(
        "/api/v1/cards",
        {"name": "Refer", "stamps_required": 5, "reward_title": "x", "referral_enabled": True},
        format="json",
    )
    assert resp.status_code == 402
    assert resp.json()["error"]["code"] == "PLAN_LIMIT"


def test_referral_enable_allowed_on_growth(merchant, monkeypatch):
    from wallets.tasks import sync_google_class

    monkeypatch.setattr(sync_google_class, "delay", lambda card_id: None)
    services.activate_plan(merchant, PlanTier.GROWTH)  # referral on
    resp = _card_client(merchant).post(
        "/api/v1/cards",
        {"name": "Refer", "stamps_required": 5, "reward_title": "x", "referral_enabled": True},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.json()["referral_enabled"] is True
