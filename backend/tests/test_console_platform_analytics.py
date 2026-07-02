"""Platform analytics & usage tests (Phase 8).

Covers the open-to-any-admin read (unlike Finance-gated revenue), and that every
aggregate matches the raw tables: merchant lifecycle counts, platform totals
(customers/cards/stamps/redemptions), wallet split, feature adoption, growth,
the acquisition funnel, and the activity leaderboard.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache

from accounts.services import settings_for
from billing.models import Invoice, InvoiceStatus
from billing.plans import BillingStatus
from billing.services import subscription_for
from console.analytics_platform import _CACHE_KEY
from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminUser
from core.enums import CardType, LedgerEvent, MerchantStatus, WalletPlatform
from core.models import Redemption, StampLedger, WalletRegistration
from messaging.enums import AutomationKey, CampaignStatus, MessageChannel
from messaging.models import Automation, Campaign
from tests import factories

pytestmark = pytest.mark.django_db

URL = "/api/admin/v1/analytics/platform"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.delete(_CACHE_KEY)
    yield
    cache.delete(_CACHE_KEY)


@pytest.fixture
def support_admin():
    a = AdminUser(email="support@stampn.net", role=AdminRole.SUPPORT)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def readonly_admin():
    a = AdminUser(email="ro@stampn.net", role=AdminRole.READ_ONLY)
    a.set_password("supersecret1")
    a.save()
    return a


def _bearer(client, admin):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return client


# ── access: any admin may read (aggregates only) ──────────────────────────────
def test_unauthenticated_rejected(api_client):
    assert api_client.get(URL).status_code == 401


def test_support_admin_allowed(api_client, support_admin):
    assert _bearer(api_client, support_admin).get(URL).status_code == 200


def test_readonly_admin_allowed(api_client, readonly_admin):
    assert _bearer(api_client, readonly_admin).get(URL).status_code == 200


# ── merchant lifecycle counts ──────────────────────────────────────────────────
def test_merchant_lifecycle_counts(api_client, support_admin):
    active = factories.MerchantFactory()
    s = subscription_for(active)
    s.status = BillingStatus.ACTIVE
    s.save()

    trial = factories.MerchantFactory()
    subscription_for(trial)  # default TRIALING, trial_ends_at = now + 14d

    locked = factories.MerchantFactory()
    ls = subscription_for(locked)
    ls.status = BillingStatus.LOCKED
    ls.save()

    # Suspended is a Merchant-level flag, independent of billing state; leave it
    # without a subscription so it doesn't skew the trialing count.
    factories.MerchantFactory(status=MerchantStatus.SUSPENDED)

    m = _bearer(api_client, support_admin).get(URL).json()["merchants"]
    assert m["total"] == 4
    assert m["active"] == 1
    assert m["trialing"] == 1
    assert m["churned"] == 1
    assert m["suspended"] == 1


# ── platform totals ─────────────────────────────────────────────────────────────
def test_platform_totals_match_raw(api_client, support_admin):
    card = factories.CardFactory()
    cc1 = factories.CustomerCardFactory(card=card, merchant=card.merchant)
    cc2 = factories.CustomerCardFactory(card=card, merchant=card.merchant)
    for cc in (cc1, cc2):
        StampLedger.objects.create(
            customer_card=cc,
            merchant=card.merchant,
            event_type=LedgerEvent.STAMP,
            delta=1,
            balance_after=1,
        )
    reward = factories.RewardFactory(card=card)
    Redemption.objects.create(customer_card=cc1, reward=reward, merchant=card.merchant)

    totals = _bearer(api_client, support_admin).get(URL).json()["totals"]
    assert totals["customers"] == 2
    assert totals["cards"] == 1
    assert totals["stamps"] == 2
    assert totals["redemptions"] == 1


# ── wallet split ────────────────────────────────────────────────────────────────
def test_wallet_split(api_client, support_admin):
    card = factories.CardFactory()
    cc = factories.CustomerCardFactory(card=card, merchant=card.merchant)
    WalletRegistration.objects.create(customer_card=cc, platform=WalletPlatform.APPLE)
    WalletRegistration.objects.create(customer_card=cc, platform=WalletPlatform.GOOGLE)
    WalletRegistration.objects.create(customer_card=cc, platform=WalletPlatform.APPLE)
    WalletRegistration.objects.create(
        customer_card=cc, platform=WalletPlatform.GOOGLE, is_active=False
    )  # inactive → excluded

    wallet = _bearer(api_client, support_admin).get(URL).json()["wallet"]
    assert wallet["apple"] == 2
    assert wallet["google"] == 1


# ── feature adoption ─────────────────────────────────────────────────────────────
def test_feature_adoption(api_client, support_admin):
    m1 = factories.MerchantFactory()
    factories.CardFactory(merchant=m1, referral_enabled=True)
    factories.CardFactory(merchant=m1, type=CardType.POINTS)
    Automation.objects.create(
        merchant=m1, key=AutomationKey.BIRTHDAY, enabled=True, channel=MessageChannel.PUSH
    )
    s = settings_for(m1)
    s.enroll_headline = "Welcome!"
    s.save()
    Campaign.objects.create(
        merchant=m1,
        channel=MessageChannel.PUSH,
        audience="all",
        message="hi",
        status=CampaignStatus.DRAFT,
    )
    # A second merchant with nothing → adoption denominators use total merchants.
    factories.MerchantFactory()

    adoption = {
        row["key"]: row
        for row in _bearer(api_client, support_admin).get(URL).json()["feature_adoption"]
    }
    assert adoption["referrals"]["merchants"] == 1
    assert adoption["points"]["merchants"] == 1
    assert adoption["automations"]["merchants"] == 1
    assert adoption["branded_enroll"]["merchants"] == 1
    assert adoption["campaigns"]["merchants"] == 1
    assert adoption["referrals"]["pct"] == pytest.approx(0.5)  # 1 of 2 merchants


def test_disabled_automation_not_counted(api_client, support_admin):
    m = factories.MerchantFactory()
    Automation.objects.create(
        merchant=m, key=AutomationKey.BIRTHDAY, enabled=False, channel=MessageChannel.PUSH
    )
    adoption = {
        row["key"]: row
        for row in _bearer(api_client, support_admin).get(URL).json()["feature_adoption"]
    }
    assert adoption["automations"]["merchants"] == 0


# ── growth + funnel ──────────────────────────────────────────────────────────────
def test_growth_and_funnel(api_client, support_admin):
    # A merchant that activated (has a card) and paid.
    paid = factories.MerchantFactory()
    factories.CardFactory(merchant=paid)
    ps = subscription_for(paid)
    ps.status = BillingStatus.ACTIVE
    ps.save()
    Invoice.objects.create(
        merchant=paid, amount_egp=299, status=InvoiceStatus.PAID, provider="paymob"
    )
    # A merchant that only signed up.
    factories.MerchantFactory()

    data = _bearer(api_client, support_admin).get(URL).json()
    growth = data["growth"]
    assert sum(g["new_merchants"] for g in growth) == 2
    assert growth[-1]["cumulative"] == 2

    funnel = {f["stage"]: f["count"] for f in data["funnel"]}
    assert funnel["signed_up"] == 2
    assert funnel["activated"] == 1
    assert funnel["active_access"] == 1
    assert funnel["paying"] == 1


# ── activity leaderboard ─────────────────────────────────────────────────────────
def test_top_merchants_by_activity(api_client, support_admin):
    busy = factories.MerchantFactory(name="Busy Cafe")
    quiet = factories.MerchantFactory(name="Quiet Cafe")
    busy_card = factories.CardFactory(merchant=busy)
    quiet_card = factories.CardFactory(merchant=quiet)
    busy_cc = factories.CustomerCardFactory(card=busy_card, merchant=busy)
    quiet_cc = factories.CustomerCardFactory(card=quiet_card, merchant=quiet)
    for _ in range(3):
        StampLedger.objects.create(
            customer_card=busy_cc,
            merchant=busy,
            event_type=LedgerEvent.STAMP,
            delta=1,
            balance_after=1,
        )
    StampLedger.objects.create(
        customer_card=quiet_cc,
        merchant=quiet,
        event_type=LedgerEvent.STAMP,
        delta=1,
        balance_after=1,
    )

    top = _bearer(api_client, support_admin).get(URL).json()["top_merchants"]
    assert top[0]["name"] == "Busy Cafe"
    assert top[0]["activity"] == 3
    assert top[0]["customers"] == 1


def test_empty_platform_is_zeroed(api_client, support_admin):
    data = _bearer(api_client, support_admin).get(URL).json()
    assert data["merchants"]["total"] == 0
    assert data["totals"]["customers"] == 0
    assert data["wallet"]["apple"] == 0
    assert all(row["pct"] == 0.0 for row in data["feature_adoption"])
    assert data["top_merchants"] == []
