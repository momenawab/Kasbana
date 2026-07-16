"""Billing models (Phase 1.4) — trial + subscription state.

Trial/subscription state lives here (a billing-owned ``Subscription``), **not**
on the frozen ``core.Merchant``: that keeps migrations inside ``billing/`` per
the brief. ``Merchant.plan`` stays as a denormalised mirror updated by the
billing webhooks; ``Subscription`` is the source of truth for *access*.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.db import models
from django.utils import timezone

from billing.plans import TRIAL_DAYS, TRIAL_PLAN, BillingInterval, BillingStatus
from core.enums import PlanTier
from core.models import Merchant, TimeStampedModel, UUIDModel
from core.tenancy import TenantManager


def default_trial_end() -> datetime:
    """Provisional trial end for a row created before a card exists.

    Under the card-upfront trial the real clock starts at card verification
    (``trial_started_at + TRIAL_DAYS``, which overwrites this). It stays as the
    field default so legacy card-free trials — and any row created outside the
    onboarding gate — still carry a bounded end date rather than ``None``, which
    ``trial_active`` would read as "no trial at all".
    """
    return timezone.now() + timedelta(days=TRIAL_DAYS)


class AnalyticsTier(models.TextChoices):
    BASIC = "basic", "Basic"
    FULL = "full", "Full"


class Plan(UUIDModel, TimeStampedModel):
    """DB-backed plan catalogue (Phase 3) — admins edit limits/features/price
    without a deploy. ``billing.plans.PLAN_LIMITS``/``PLAN_PRICES_EGP`` remain the
    seed data (loaded by a data migration) and the in-code fallback used when
    this table is empty; see ``billing.plans.plan_limits_map``.

    ``key`` matches a ``core.enums.PlanTier`` value for the shipped tiers, but is
    a plain string so custom/negotiated plans can be added without a code change.
    Archived (not deleted) so historical subscriptions keep a valid reference.
    """

    key = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    price_egp = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    # Annual list price — ten months' worth of ``price_egp`` ("2 months free").
    price_egp_annual = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    is_public = models.BooleanField(default=True)  # offered on the self-serve subscribe screen
    archived = models.BooleanField(default=False)

    # The Paymob Subscription Plan this tier maps to, one per interval. Created
    # once per environment by ``manage.py create_paymob_plans`` and pasted back
    # here; blank until then (and always blank for FREE, which isn't sellable).
    paymob_plan_id_monthly = models.CharField(max_length=64, blank=True)
    paymob_plan_id_annual = models.CharField(max_length=64, blank=True)

    # ``max_*`` — null means unlimited (mirrors billing.plans.LIMIT_CAPABILITIES).
    max_cards = models.PositiveIntegerField(null=True, blank=True)
    max_locations = models.PositiveIntegerField(null=True, blank=True)
    max_staff = models.PositiveIntegerField(null=True, blank=True)
    max_customers = models.PositiveIntegerField(null=True, blank=True)

    export = models.BooleanField(default=False)
    api = models.BooleanField(default=False)
    specialized_roles = models.BooleanField(default=False)
    custom_branding = models.BooleanField(default=False)
    referral = models.BooleanField(default=False)

    automations = models.PositiveIntegerField(default=0)
    analytics = models.CharField(
        max_length=8, choices=AnalyticsTier.choices, default=AnalyticsTier.BASIC
    )

    class Meta:
        ordering = ["price_egp", "key"]

    def __str__(self) -> str:
        return f"{self.key} ({self.name})"

    def paymob_plan_id(self, interval: str) -> str:
        """The Paymob Subscription Plan id for ``interval``, or "" if unmapped."""
        if interval == BillingInterval.ANNUAL:
            return self.paymob_plan_id_annual
        return self.paymob_plan_id_monthly

    def as_limits(self) -> dict[str, int | bool | str | None]:
        """Shape matching ``billing.plans.PLAN_LIMITS[plan]`` for the entitlements engine."""
        return {
            "max_cards": self.max_cards,
            "max_locations": self.max_locations,
            "max_staff": self.max_staff,
            "max_customers": self.max_customers,
            "export": self.export,
            "api": self.api,
            "specialized_roles": self.specialized_roles,
            "custom_branding": self.custom_branding,
            "referral": self.referral,
            "automations": self.automations,
            "analytics": self.analytics,
        }


class Subscription(UUIDModel, TimeStampedModel):
    """One subscription per merchant; drives the entitlements engine."""

    merchant = models.OneToOneField(Merchant, on_delete=models.CASCADE, related_name="subscription")
    # The plan the merchant picked at the gate — what they trial on and what
    # Paymob auto-charges at trial end (see ``effective_plan``).
    plan = models.CharField(max_length=16, choices=PlanTier.choices, default=PlanTier.FREE)
    status = models.CharField(
        max_length=24, choices=BillingStatus.choices, default=BillingStatus.TRIALING
    )
    # How often the plan renews; picked alongside ``plan`` at the gate and fixed
    # for the life of the Paymob subscription (switching interval re-subscribes).
    billing_interval = models.CharField(
        max_length=8, choices=BillingInterval.choices, default=BillingInterval.MONTHLY
    )
    trial_ends_at = models.DateTimeField(null=True, blank=True, default=default_trial_end)
    current_period_end = models.DateTimeField(null=True, blank=True)
    # Gateway linkage (Paymob) — filled by the webhook handlers.
    provider = models.CharField(max_length=16, blank=True)
    gateway_ref = models.CharField(max_length=128, blank=True)

    # ── Recurring subscription + card-upfront trial ─────────────────────────
    # Paymob's *subscription* instance id — distinct from ``gateway_ref``, which
    # stays the linking *transaction* ref. Needed to suspend/resume/cancel the
    # recurring deductions on Paymob's side.
    paymob_subscription_id = models.CharField(max_length=64, blank=True)
    # When the card was verified and the trial clock actually started. Null while
    # PENDING_CARD; ``trial_ends_at`` is derived from it (+ TRIAL_DAYS) rather
    # than from signup, since a trial without a card never begins.
    trial_started_at = models.DateTimeField(null=True, blank=True)
    card_verified = models.BooleanField(default=False)
    card_token_ref = models.CharField(max_length=64, blank=True)  # Paymob card token
    # The plan a pending checkout will convert to, recorded at ``subscribe`` time
    # so the webhook (which only carries a gateway ref) knows what to activate.
    pending_plan = models.CharField(max_length=16, choices=PlanTier.choices, blank=True)
    # Merchant-initiated cancellation that keeps access until the paid period
    # ends (contract "cancel = retain until period end"). While True the sub
    # stays ACTIVE and fully entitled until ``current_period_end``; after that
    # ``effective_plan`` locks it. Cleared on any re-subscribe (``activate_plan``).
    cancel_at_period_end = models.BooleanField(default=False)

    # ── Admin manual-control fields (Phase 4) ───────────────────────────────
    # ``comp``: free access granted by an admin — access resolves at ``plan``
    # regardless of billing ``status`` (locked/canceled/past-due included).
    comp = models.BooleanField(default=False)
    # ``override_plan``: temporarily force a specific plan's limits, independent
    # of ``plan``/``status`` — e.g. a goodwill upgrade, or an emergency downgrade
    # while a billing issue is resolved. Takes precedence over everything else,
    # including a lock, so support can always use it to unblock a merchant.
    override_plan = models.CharField(max_length=16, choices=PlanTier.choices, blank=True)
    override_expires_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        # Platform analytics counts subscriptions by status (active / trialing /
        # past_due / churned) on every dashboard load — index the status column.
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"{self.merchant_id} · {self.status} · {self.plan}"

    def trial_active(self, now: datetime | None = None) -> bool:
        now = now or timezone.now()
        return (
            self.status == BillingStatus.TRIALING
            and self.trial_ends_at is not None
            and self.trial_ends_at > now
        )

    def override_active(self, now: datetime | None = None) -> bool:
        now = now or timezone.now()
        return bool(self.override_plan) and (
            self.override_expires_at is None or self.override_expires_at > now
        )

    def cancels_on(self, now: datetime | None = None) -> datetime | None:
        """The date a scheduled cancellation takes effect, or ``None``.

        Set only while a merchant-initiated period-end cancel is pending and the
        period hasn't lapsed yet — drives the "cancels on <date>" UI. Once the
        date passes, ``effective_plan`` locks the sub and this returns ``None``.
        A paid sub runs out at ``current_period_end``; a trial at ``trial_ends_at``.
        """
        now = now or timezone.now()
        if not self.cancel_at_period_end:
            return None
        end = self.current_period_end if self.status == BillingStatus.ACTIVE else self.trial_ends_at
        return end if end is not None and end > now else None

    def effective_plan(self, now: datetime | None = None) -> str | None:
        """The plan whose limits apply right now, or ``None`` when locked.

        - an active admin override -> ``override_plan``, regardless of status;
        - ``comp`` -> the stored ``plan``, regardless of status;
        - PENDING_CARD -> locked (``None``) — signed up but no card yet, so the
          trial has not started (the onboarding gate is the only reachable UI);
        - TRIALING + not expired -> the ``plan`` they picked at the gate;
        - TRIALING + expired      -> locked (``None``) — trial ended unconverted;
        - ACTIVE                  -> the paid ``plan`` (until a scheduled
          period-end cancel lapses, then locked — access retained meanwhile);
        - PAST_DUE / CANCELED / LOCKED -> locked (``None``), data retained.
        """
        now = now or timezone.now()
        if self.override_active(now):
            return self.override_plan
        if self.comp:
            return self.plan
        if self.status == BillingStatus.TRIALING:
            if not self.trial_active(now):
                return None
            # Legacy rows started a card-free trial before a plan was ever
            # picked, so ``plan`` is still FREE for them — those keep the old
            # fixed Growth-level trial. New signups always arrive here with the
            # tier they chose at the gate.
            return self.plan if self.plan != PlanTier.FREE else TRIAL_PLAN
        if self.status == BillingStatus.ACTIVE:
            # A period-end cancel keeps access until the period lapses, then locks.
            if (
                self.cancel_at_period_end
                and self.current_period_end is not None
                and now >= self.current_period_end
            ):
                return None
            return self.plan
        return None


class InvoiceStatus(models.TextChoices):
    """Contract ``Invoice.status`` values (lowercase wire format)."""

    PAID = "paid", "Paid"
    PENDING = "pending", "Pending"
    FAILED = "failed", "Failed"


class Invoice(UUIDModel, TimeStampedModel):
    """A billing invoice, created by the gateway webhook on a successful charge.

    Tenant-scoped via ``merchant``; ``gateway_ref`` links it back to the
    Paymob transaction so webhook replays are idempotent.
    """

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="invoices")
    amount_egp = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=16, choices=InvoiceStatus.choices, default=InvoiceStatus.PENDING
    )
    issued_at = models.DateTimeField(default=timezone.now)
    pdf_url = models.URLField(blank=True)
    provider = models.CharField(max_length=16, blank=True)
    gateway_ref = models.CharField(max_length=128, blank=True)
    # Admin-only memo for manual/one-off invoices (Phase 5) — NOT in the frozen
    # merchant contract's Invoice shape, so InvoiceSerializer never exposes it.
    note = models.TextField(blank=True)

    objects = TenantManager()

    class Meta:
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["merchant", "-issued_at"]),
            # Revenue analytics scans PAID invoices by issue date cross-tenant
            # (MRR, month buckets, payer set) — the merchant-leading index above
            # can't serve those, so index (status, issued_at) too.
            models.Index(fields=["status", "issued_at"]),
        ]
        constraints = [
            # DB-level guarantee that a replayed (or concurrent duplicate) webhook
            # can't create a second invoice for the same gateway transaction.
            # Manual invoices (blank gateway_ref) are exempt.
            models.UniqueConstraint(
                fields=["provider", "gateway_ref"],
                condition=~models.Q(gateway_ref=""),
                name="uniq_invoice_provider_gateway_ref",
            )
        ]

    def __str__(self) -> str:
        return f"{self.merchant_id} · {self.amount_egp} EGP · {self.status}"


class CouponGroup(UUIDModel, TimeStampedModel):
    """A named grouping over individually-created coupons (Phase 11 deferral).

    Purely organisational — coupons work exactly as before whether grouped or
    not. A coupon's ``group`` is optional and ``SET_NULL`` on delete, so removing
    a group never removes its coupons; they simply become ungrouped again.
    """

    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class Coupon(UUIDModel, TimeStampedModel):
    """A discount/promo code (Phase 11) — billing-owned config, admin-managed.

    ``percent``/``fixed`` reduce a subscribe/checkout charge; ``free_months``/
    ``trial_extension`` are admin-granted directly to a merchant (no checkout).
    Caps are enforced server-side in ``billing.coupons``.
    """

    class Type(models.TextChoices):
        PERCENT = "percent", "Percent off"
        FIXED = "fixed", "Fixed EGP off"
        FREE_MONTHS = "free_months", "Free months (comp)"
        TRIAL_EXTENSION = "trial_extension", "Trial extension (days)"

    code = models.CharField(max_length=32, unique=True)  # stored uppercased
    type = models.CharField(max_length=16, choices=Type.choices)
    value = models.DecimalField(max_digits=10, decimal_places=2)  # % | EGP | months | days
    # Empty list = every plan; else the PlanTier keys the code is valid for.
    plan_scope = models.JSONField(default=list, blank=True)
    max_redemptions = models.IntegerField(null=True, blank=True)  # null = unlimited
    per_merchant_once = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    redemption_count = models.IntegerField(default=0)  # denormalised for cap checks
    # Optional organisational grouping (Phase 11 deferral). Blank/null = ungrouped,
    # today's behaviour. SET_NULL so deleting a group never deletes its coupons.
    group = models.ForeignKey(
        CouponGroup,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="coupons",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.code} ({self.type} {self.value})"


class CouponRedemption(UUIDModel):
    """One application of a coupon to a merchant (Phase 11) — the report + cap
    source of truth."""

    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="redemptions")
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="coupon_redemptions"
    )
    discount_egp = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    detail = models.CharField(max_length=120, blank=True)  # e.g. "trial +14d", "GROWTH -20%"
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.coupon_id} → {self.merchant_id}"


class WebhookDelivery(UUIDModel, TimeStampedModel):
    """A received gateway webhook (Phase 14 ops log).

    Recorded by the webhook views so the ops console can inspect deliveries and
    replay a failed one. ``payload`` holds the parsed event fields (not the raw
    signed body), which is all ``apply_webhook_event`` needs for a replay.
    Recording never blocks the webhook ack — write failures are swallowed.
    """

    class Status(models.TextChoices):
        PROCESSED = "processed", "Processed"
        NO_MERCHANT = "no_merchant", "No merchant matched"
        INVALID = "invalid", "Invalid signature"
        DISABLED = "disabled", "Provider disabled"
        FAILED = "failed", "Processing failed"

    provider = models.CharField(max_length=16)
    kind = models.CharField(max_length=24, blank=True)  # success/failed/canceled/ignored
    gateway_ref = models.CharField(max_length=128, blank=True)
    # Not an FK: the merchant may be gone (erased) but we still keep the log row.
    merchant_id_hint = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    payload = models.JSONField(default=dict, blank=True)  # parsed event fields, for replay
    error = models.CharField(max_length=500, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["provider", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider} · {self.kind or '?'} · {self.status}"
