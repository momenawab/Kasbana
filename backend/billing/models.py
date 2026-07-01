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

from billing.plans import TRIAL_DAYS, TRIAL_PLAN, BillingStatus
from core.enums import PlanTier
from core.models import Merchant, TimeStampedModel, UUIDModel
from core.tenancy import TenantManager


def default_trial_end() -> datetime:
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
    is_public = models.BooleanField(default=True)  # offered on the self-serve subscribe screen
    archived = models.BooleanField(default=False)

    # ``max_*`` — null means unlimited (mirrors billing.plans.LIMIT_CAPABILITIES).
    max_cards = models.PositiveIntegerField(null=True, blank=True)
    max_locations = models.PositiveIntegerField(null=True, blank=True)
    max_staff = models.PositiveIntegerField(null=True, blank=True)
    max_customers = models.PositiveIntegerField(null=True, blank=True)

    whatsapp = models.BooleanField(default=False)
    export = models.BooleanField(default=False)
    api = models.BooleanField(default=False)
    specialized_roles = models.BooleanField(default=False)
    custom_branding = models.BooleanField(default=False)

    automations = models.PositiveIntegerField(default=0)
    analytics = models.CharField(
        max_length=8, choices=AnalyticsTier.choices, default=AnalyticsTier.BASIC
    )
    whatsapp_quota = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["price_egp", "key"]

    def __str__(self) -> str:
        return f"{self.key} ({self.name})"

    def as_limits(self) -> dict[str, int | bool | str | None]:
        """Shape matching ``billing.plans.PLAN_LIMITS[plan]`` for the entitlements engine."""
        return {
            "max_cards": self.max_cards,
            "max_locations": self.max_locations,
            "max_staff": self.max_staff,
            "max_customers": self.max_customers,
            "whatsapp": self.whatsapp,
            "export": self.export,
            "api": self.api,
            "specialized_roles": self.specialized_roles,
            "custom_branding": self.custom_branding,
            "automations": self.automations,
            "analytics": self.analytics,
            "whatsapp_quota": self.whatsapp_quota,
        }


class Subscription(UUIDModel, TimeStampedModel):
    """One subscription per merchant; drives the entitlements engine."""

    merchant = models.OneToOneField(Merchant, on_delete=models.CASCADE, related_name="subscription")
    # The paid plan the merchant converts to; during the trial, access is
    # TRIAL_PLAN-level regardless of this value (see ``effective_plan``).
    plan = models.CharField(max_length=16, choices=PlanTier.choices, default=PlanTier.FREE)
    status = models.CharField(
        max_length=16, choices=BillingStatus.choices, default=BillingStatus.TRIALING
    )
    trial_ends_at = models.DateTimeField(null=True, blank=True, default=default_trial_end)
    current_period_end = models.DateTimeField(null=True, blank=True)
    # Gateway linkage (Paymob / Fawry) — filled by the webhook handlers.
    provider = models.CharField(max_length=16, blank=True)
    gateway_ref = models.CharField(max_length=128, blank=True)
    # The plan a pending checkout will convert to, recorded at ``subscribe`` time
    # so the webhook (which only carries a gateway ref) knows what to activate.
    pending_plan = models.CharField(max_length=16, choices=PlanTier.choices, blank=True)

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

    def effective_plan(self, now: datetime | None = None) -> str | None:
        """The plan whose limits apply right now, or ``None`` when locked.

        - an active admin override -> ``override_plan``, regardless of status;
        - ``comp`` -> the stored ``plan``, regardless of status;
        - TRIALING + not expired -> ``TRIAL_PLAN`` (full Growth-level access);
        - TRIALING + expired      -> locked (``None``) — trial ended unconverted;
        - ACTIVE                  -> the paid ``plan``;
        - PAST_DUE / CANCELED / LOCKED -> locked (``None``), data retained.
        """
        now = now or timezone.now()
        if self.override_active(now):
            return self.override_plan
        if self.comp:
            return self.plan
        if self.status == BillingStatus.TRIALING:
            return TRIAL_PLAN if self.trial_active(now) else None
        if self.status == BillingStatus.ACTIVE:
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
    Paymob/Fawry transaction so webhook replays are idempotent.
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

    objects = TenantManager()

    class Meta:
        ordering = ["-issued_at"]
        indexes = [models.Index(fields=["merchant", "-issued_at"])]
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
