"""Billing models (Phase 1.4) — trial + subscription state.

Trial/subscription state lives here (a billing-owned ``Subscription``), **not**
on the frozen ``core.Merchant``: that keeps migrations inside ``billing/`` per
the brief. ``Merchant.plan`` stays as a denormalised mirror updated by the
billing webhooks; ``Subscription`` is the source of truth for *access*.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.db import models
from django.utils import timezone

from billing.plans import TRIAL_DAYS, TRIAL_PLAN, BillingStatus
from core.enums import PlanTier
from core.models import Merchant, TimeStampedModel, UUIDModel
from core.tenancy import TenantManager


def default_trial_end() -> datetime:
    return timezone.now() + timedelta(days=TRIAL_DAYS)


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

    def __str__(self) -> str:
        return f"{self.merchant_id} · {self.status} · {self.plan}"

    def trial_active(self, now: datetime | None = None) -> bool:
        now = now or timezone.now()
        return (
            self.status == BillingStatus.TRIALING
            and self.trial_ends_at is not None
            and self.trial_ends_at > now
        )

    def effective_plan(self, now: datetime | None = None) -> str | None:
        """The plan whose limits apply right now, or ``None`` when locked.

        - TRIALING + not expired -> ``TRIAL_PLAN`` (full Growth-level access);
        - TRIALING + expired      -> locked (``None``) — trial ended unconverted;
        - ACTIVE                  -> the paid ``plan``;
        - PAST_DUE / CANCELED / LOCKED -> locked (``None``), data retained.
        """
        now = now or timezone.now()
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

    def __str__(self) -> str:
        return f"{self.merchant_id} · {self.amount_egp} EGP · {self.status}"
