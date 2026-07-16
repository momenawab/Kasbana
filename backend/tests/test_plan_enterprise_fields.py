"""Plan fields that exist for Enterprise (§12.4) — campaigns, support, extras.

All three are inert on the public tiers by design: campaigns have never been
capped and priority support is a negotiated term, so this must change nothing
for an existing merchant. What's asserted here is mostly that.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from billing import entitlements, services
from billing.models import Plan
from billing.plans import PLAN_LIMITS, invalidate_plan_cache
from common.errors import PlanLimit
from core.enums import PlanTier
from messaging.models import Campaign
from tests import factories

pytestmark = pytest.mark.django_db


def _enterprise(merchant, **fields) -> Plan:
    """An admin-defined Enterprise plan, assigned the only way possible today
    (the FK arrives in stage 3): by pointing the merchant's plan at its key."""
    plan = Plan.objects.create(
        key="ENT_GOLD",
        name="Enterprise Gold",
        price_egp=Decimal("7500"),
        price_egp_annual=Decimal("75000"),
        is_public=False,
        **fields,
    )
    invalidate_plan_cache()
    sub = services.subscription_for(merchant)  # created lazily on first access
    sub.plan = plan.key
    sub.status = "ACTIVE"
    sub.save()
    return plan


# ── Nothing changes for the public tiers ────────────────────────────────────
@pytest.mark.parametrize("tier", [PlanTier.STARTER, PlanTier.GROWTH, PlanTier.CHAIN])
def test_public_tiers_have_unlimited_campaigns(tier):
    """Campaigns were never capped; introducing the field must not cap them."""
    assert PLAN_LIMITS[tier]["max_campaigns_per_month"] is None


@pytest.mark.parametrize("tier", [PlanTier.STARTER, PlanTier.GROWTH, PlanTier.CHAIN])
def test_priority_support_is_off_on_public_tiers(tier):
    assert PLAN_LIMITS[tier]["priority_support"] is False


def test_no_plan_can_remove_the_powered_by_footer():
    """Confirmed 2026-07-16: there is no option to remove "Powered by Stampn",
    on any plan, Enterprise included. A white_label flag must never appear."""
    from billing.plans import FEATURE_CAPABILITIES

    assert "white_label" not in FEATURE_CAPABILITIES
    for tier in PLAN_LIMITS:
        assert "white_label" not in PLAN_LIMITS[tier]


def test_a_growth_merchant_can_still_create_campaigns(merchant):
    assert entitlements.check(merchant, "max_campaigns_per_month") is True


# ── The campaign allowance ──────────────────────────────────────────────────
def test_enterprise_can_cap_campaigns_per_month(merchant):
    _enterprise(merchant, max_campaigns_per_month=2)

    for _ in range(2):
        Campaign.objects.create(merchant=merchant, audience="all", message="hi")

    assert entitlements.check(merchant, "max_campaigns_per_month") is False
    with pytest.raises(PlanLimit):
        entitlements.enforce(merchant, "max_campaigns_per_month")


def test_the_allowance_is_monthly_not_lifetime(merchant):
    """The whole point of per-month: a lifetime cap would block a long-lived
    merchant permanently instead of pacing them."""
    _enterprise(merchant, max_campaigns_per_month=2)

    # Two from a previous month — spent, but not against this month.
    for _ in range(2):
        c = Campaign.objects.create(merchant=merchant, audience="all", message="old")
        Campaign.objects.filter(pk=c.pk).update(created_at=timezone.now() - timedelta(days=45))

    assert entitlements.check(merchant, "max_campaigns_per_month") is True
    assert entitlements.usage(merchant)["campaigns_this_month"] == 0


def test_the_allowance_is_scoped_to_the_merchant(merchant):
    _enterprise(merchant, max_campaigns_per_month=1)
    other = factories.MerchantFactory()
    Campaign.objects.create(merchant=other, audience="all", message="theirs")

    # Someone else's campaign must not spend our allowance.
    assert entitlements.check(merchant, "max_campaigns_per_month") is True


def test_usage_reports_campaigns_for_the_current_month(merchant):
    Campaign.objects.create(merchant=merchant, audience="all", message="hi")

    assert entitlements.usage(merchant)["campaigns_this_month"] == 1


# ── Negotiated extras ───────────────────────────────────────────────────────
def test_custom_features_carry_negotiated_terms(merchant):
    _enterprise(merchant, custom_features={"sso": True, "pos_sync": "two_way"})

    assert entitlements.custom_feature(merchant, "sso") is True
    assert entitlements.custom_feature(merchant, "pos_sync") == "two_way"


def test_an_unnegotiated_custom_feature_is_absent_not_an_error(merchant):
    """Free-form by design, so a missing key is a legitimate "not agreed" —
    unlike check(), where an unknown capability must stay an error."""
    _enterprise(merchant, custom_features={"sso": True})

    assert entitlements.custom_feature(merchant, "never_agreed") is None
    assert entitlements.custom_feature(merchant, "never_agreed", default=False) is False


def test_custom_features_default_to_empty_on_a_public_tier(merchant):
    assert entitlements.custom_feature(merchant, "sso") is None


def test_a_locked_merchant_gets_no_negotiated_extras(merchant):
    _enterprise(merchant, custom_features={"sso": True})
    sub = services.subscription_for(merchant)
    sub.status = "LOCKED"
    sub.save()

    assert entitlements.custom_feature(merchant, "sso") is None


def test_a_hand_broken_custom_features_does_not_explode(merchant):
    """The column is free-form JSON an admin edits; a list where a dict belongs
    must degrade, not 500 every gated request."""
    _enterprise(merchant, custom_features=["oops"])

    assert entitlements.custom_feature(merchant, "sso") is None


def test_entitlements_expose_the_new_fields(merchant):
    _enterprise(merchant, priority_support=True, custom_features={"sso": True})

    described = entitlements.describe(merchant)

    assert described["features"]["priority_support"] is True
    assert described["features"]["custom_features"] == {"sso": True}
    assert described["limits"]["max_campaigns_per_month"] is None
