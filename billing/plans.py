"""Plan catalogue — limits + feature flags per ``PlanTier`` (Phase 1.4).

The frozen contract pins the anti-fraud constants but **not** the per-plan
limits, so this map is billing-owned config (not a contract symbol): tune the
numbers here without a contract PR. ``None`` means *unlimited*.

The entitlements engine (``billing/entitlements.py``) reads this map; the trial
gives full ``TRIAL_PLAN``-level access for ``TRIAL_DAYS`` regardless of the
merchant's stored plan, then locks on expiry without conversion.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

from django.core.cache import cache
from django.db import models

from core.enums import PlanTier

# One plan's capability map. Values are a limit (``int``/``None``), a feature
# flag (``bool``), a tier name (``str`` — ``analytics``), or the free-form
# ``custom_features`` object, hence the ``dict`` member.
PlanLimitValue = int | bool | str | None | dict[str, object]
PlanLimits = dict[str, PlanLimitValue]


class BillingStatus(models.TextChoices):
    """Lifecycle of a merchant's subscription (billing-owned, not in core)."""

    # Signed up, but no plan picked / no card verified yet — the trial clock has
    # not started and access is locked (``effective_plan`` -> None). The merchant
    # leaves this state by completing the 1 EGP card verification, which starts
    # the trial and creates the Paymob subscription.
    PENDING_CARD = "PENDING_CARD", "Pending card"
    TRIALING = "TRIALING", "Trialing"
    ACTIVE = "ACTIVE", "Active"
    PAST_DUE = "PAST_DUE", "Past due"
    CANCELED = "CANCELED", "Canceled"
    LOCKED = "LOCKED", "Locked"


class BillingInterval(models.TextChoices):
    """How often a subscription auto-renews. Mirrors the pricing page's toggle
    and the two Paymob Subscription Plans created per tier (30d / 360d)."""

    MONTHLY = "monthly", "Monthly"
    ANNUAL = "annual", "Annual"


# Paymob only accepts a frequency from this fixed enum — anything else fails the
# plan creation with 400 {"frequency": ["\"5\" is not a valid choice."]}.
PAYMOB_FREQUENCIES = frozenset({7, 15, 30, 60, 90, 180, 360})

# Paymob plan frequency, in days, per interval — the ``frequency`` field on a
# Paymob Subscription Plan and the amount ``current_period_end`` rolls forward
# by on each successful renewal. 30 = Paymob's "Monthly", 360 = its "Yearly";
# note annual is 360 days, not 365, so it is not a calendar year.
INTERVAL_DAYS: dict[str, int] = {
    BillingInterval.MONTHLY: 30,
    BillingInterval.ANNUAL: 360,
}

# 14-day trial (brief §1.4). Historically the trial granted fixed Growth-level
# access; under the card-upfront trial the merchant picks a tier at signup and
# trials on *that* tier, so ``TRIAL_PLAN`` is now only the fallback for legacy
# rows that started a trial before a plan was ever selected.
TRIAL_DAYS = 14
TRIAL_PLAN = PlanTier.GROWTH

# The 1 EGP card-verification charge (in piastres) that tokenises the card and
# acts as the linking transaction for the Paymob subscription. Deliberately not
# refunded — it appears on the statement as proof of a valid card.
CARD_VERIFICATION_AMOUNT_CENTS = 100

# Capability groups. ``max_*`` are counted against live usage; the rest are
# boolean feature flags. Keep in sync with ``entitlements.CAPABILITIES``.
LIMIT_CAPABILITIES = frozenset(
    {
        "max_cards",
        "max_locations",
        "max_staff",
        "max_customers",
        # Counted per calendar month, not lifetime — campaigns accumulate
        # forever, so a lifetime cap would permanently block a long-lived
        # merchant rather than pace them. Unlimited on every public tier
        # (campaigns have never been capped); it exists for Enterprise plans,
        # where an admin negotiates a number.
        "max_campaigns_per_month",
    }
)
# ``specialized_roles`` gates the Marketing/Designer staff roles; ``custom_branding``
# gates custom join-page branding (the "Powered by Stampn" footer is mandatory on
# every plan and cannot be removed). Both Growth+.
# ``priority_support`` is an Enterprise-negotiated term (dedicated/priority
# response). It gates nothing in the product today — it is a contractual promise
# support staff act on — but it lives here so the admin can set it per plan and
# the merchant can see what they bought.
#
# There is deliberately no ``white_label``: "Powered by Stampn" cannot be
# removed on any plan, Enterprise included (confirmed 2026-07-16). Do not add
# one; the footer is not a negotiable term.
FEATURE_CAPABILITIES = frozenset(
    {"export", "api", "specialized_roles", "custom_branding", "referral", "priority_support"}
)
# Derived capabilities are computed from a non-boolean plan field, not a stored
# flag. ``analytics_full`` is true when the plan's ``analytics`` tier is "full"
# (Growth+); Starter/Free are "basic". It gates the deep analytics views
# (timeseries/retention/wallet_split/by_location); the summary stays basic.
DERIVED_CAPABILITIES = frozenset({"analytics_full"})

# plan -> {capability: limit|flag}. ``None`` limit = unlimited.
# ``automations`` (int) and ``analytics`` (basic|full) are display-only features
# surfaced via /me's Entitlements — not gate capabilities, so they are NOT in
# FEATURE_CAPABILITIES and never passed to ``entitlements.check()``.
#
# FREE is not a sellable tier (subscribe offers Starter/Growth/Chain only) — it
# only supplies the display "shape" for a locked/un-converted account, so it
# stays here to avoid a KeyError but grants nothing.
PLAN_LIMITS: dict[str, PlanLimits] = {
    PlanTier.FREE: {
        "max_cards": 1,
        "max_locations": 1,
        "max_staff": 2,
        "max_customers": 200,
        "export": False,
        "api": False,
        "specialized_roles": False,
        "custom_branding": False,
        "referral": False,
        "priority_support": False,
        "custom_features": {},
        "max_campaigns_per_month": None,
        "automations": 0,
        "analytics": "basic",
    },
    PlanTier.STARTER: {
        "max_cards": 3,
        "max_locations": 2,
        "max_staff": 5,
        "max_customers": 2_000,
        "export": True,
        "api": False,
        "specialized_roles": False,
        "custom_branding": False,
        "referral": False,
        "priority_support": False,
        "custom_features": {},
        "max_campaigns_per_month": None,
        # Engagement automations are a Growth+ feature; `welcome` is exempt (free
        # on every plan). 0 here means Starter can enable no engagement automation.
        "automations": 0,
        "analytics": "basic",
    },
    PlanTier.GROWTH: {
        "max_cards": 10,
        "max_locations": 10,
        "max_staff": 25,
        "max_customers": 20_000,
        "export": True,
        # API is not a self-serve ladder feature — it's bespoke, Enterprise-only.
        "api": False,
        "specialized_roles": True,
        "custom_branding": True,
        "referral": True,
        "priority_support": False,
        "custom_features": {},
        "max_campaigns_per_month": None,
        "automations": 5,
        "analytics": "full",
    },
    PlanTier.CHAIN: {
        "max_cards": None,
        "max_locations": None,
        "max_staff": None,
        "max_customers": None,
        "export": True,
        "api": False,
        "specialized_roles": True,
        "custom_branding": True,
        "referral": True,
        "priority_support": False,
        "custom_features": {},
        "max_campaigns_per_month": None,
        "automations": 99,
        "analytics": "full",
    },
}

# Monthly list price per tier, EGP major units (billing-owned config). Every
# tier here is self-service and really charges this — including CHAIN, which an
# older comment described as "custom-quoted / contact us"; negotiated deals are
# the separate Enterprise tier, not a mode of Chain (revised 2026-07-16).
PLAN_PRICES_EGP: dict[str, Decimal] = {
    PlanTier.FREE: Decimal("0"),
    PlanTier.STARTER: Decimal("599"),
    PlanTier.GROWTH: Decimal("999"),
    PlanTier.CHAIN: Decimal("2499"),
}

# Annual list price per tier — ten months' worth of the monthly price, i.e. the
# "2 months free" framing the marketing pricing toggle already advertises.
PLAN_PRICES_EGP_ANNUAL: dict[str, Decimal] = {
    PlanTier.FREE: Decimal("0"),
    PlanTier.STARTER: Decimal("5990"),
    PlanTier.GROWTH: Decimal("9990"),
    PlanTier.CHAIN: Decimal("24990"),
}

# Phase 3 — plan limits AND prices move to the DB (``billing.models.Plan``) so
# admins can edit them without a deploy. ``PLAN_LIMITS`` / ``PLAN_PRICES_EGP``
# above stay as the seed data (a migration loads them) and the fallback below
# when the table is empty/missing a key — e.g. a fresh install before the seed
# migration runs, or isolated unit tests that touch ``billing.plans`` w/o the DB.
# v3 — entries gained ``price_annual``; a stale v2 entry would KeyError.
_PLAN_CATALOGUE_CACHE_KEY = "billing:plan_catalogue:v3"
_PLAN_CATALOGUE_CACHE_TTL = 60  # seconds; admin edits also invalidate explicitly


class _PlanEntry(TypedDict):
    limits: PlanLimits
    price: Decimal
    price_annual: Decimal


def _catalogue() -> dict[str, _PlanEntry]:
    """DB-backed ``{key: {limits, price}}`` for **all** plans, cached.

    Archived plans are included on purpose: archiving only hides a plan from the
    catalogue *listing* (admin/subscribe UI) — it must not change how an existing
    subscriber's limits or price resolve. Empty (fresh install) -> ``{}`` so the
    accessors below fall back to the hardcoded seed.
    """
    cached = cache.get(_PLAN_CATALOGUE_CACHE_KEY)
    if cached is not None:
        return cached

    from billing.models import Plan  # local import: Plan lives in this app's models

    rows: dict[str, _PlanEntry] = {
        p.key: {
            "limits": p.as_limits(),
            "price": p.price_egp,
            "price_annual": p.price_egp_annual,
        }
        for p in Plan.objects.all()
    }
    cache.set(_PLAN_CATALOGUE_CACHE_KEY, rows, _PLAN_CATALOGUE_CACHE_TTL)
    return rows


def plan_limits_map() -> dict[str, PlanLimits]:
    """The live plan -> limits map, DB-backed with the hardcoded seed as fallback."""
    rows = {key: entry["limits"] for key, entry in _catalogue().items()}
    return rows or PLAN_LIMITS


def plan_price(plan: str, interval: str = BillingInterval.MONTHLY) -> Decimal:
    """The live price for ``plan`` at ``interval`` (what checkout charges), DB-backed.

    Defaults to monthly so existing monthly-only callers (revenue analytics'
    MRR, coupon discounts) keep their meaning.
    """
    annual = interval == BillingInterval.ANNUAL
    entry = _catalogue().get(plan)
    if entry is not None:
        return entry["price_annual"] if annual else entry["price"]
    seed = PLAN_PRICES_EGP_ANNUAL if annual else PLAN_PRICES_EGP
    return seed.get(plan, Decimal("0"))


def invalidate_plan_cache() -> None:
    """Call after any ``Plan`` create/update/archive so edits apply immediately."""
    cache.delete(_PLAN_CATALOGUE_CACHE_KEY)
