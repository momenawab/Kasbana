"""Messaging models (Phase 1.7) — campaigns, automations, WhatsApp metering.

A new ``messaging/`` app (queue ``messaging`` already configured). All three
models are tenant-scoped via a ``merchant`` FK and use the shared
``TenantManager`` so every queryset goes through ``for_merchant``.
"""

from __future__ import annotations

from datetime import date

from django.db import models
from django.utils import timezone

from core.models import Merchant, TimeStampedModel, UUIDModel
from core.tenancy import TenantManager
from messaging.enums import AutomationKey, CampaignStatus, MessageChannel


class Campaign(UUIDModel, TimeStampedModel):
    """A one-shot broadcast to a computed audience (segment key)."""

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="campaigns")
    channel = models.CharField(max_length=16, choices=MessageChannel.choices)
    audience = models.CharField(max_length=64)  # a segment key (e.g. "lapsed")
    message = models.TextField()
    status = models.CharField(
        max_length=16, choices=CampaignStatus.choices, default=CampaignStatus.DRAFT
    )
    schedule_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered = models.IntegerField(default=0)
    opened = models.IntegerField(default=0)

    objects = TenantManager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.channel} → {self.audience} ({self.status})"


class Automation(UUIDModel, TimeStampedModel):
    """A per-merchant lifecycle trigger; one row per ``AutomationKey``."""

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="automations")
    key = models.CharField(max_length=24, choices=AutomationKey.choices)
    enabled = models.BooleanField(default=False)
    channel = models.CharField(
        max_length=16, choices=MessageChannel.choices, default=MessageChannel.PUSH
    )
    timing = models.CharField(max_length=64, blank=True)  # free-form (e.g. "+7d")
    template = models.TextField(blank=True)

    objects = TenantManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "key"], name="uniq_merchant_automation_key")
        ]

    def __str__(self) -> str:
        return f"{self.merchant_id} · {self.key} ({'on' if self.enabled else 'off'})"


class WhatsAppUsage(models.Model):
    """Per-merchant per-month WhatsApp send counter (drives quota metering).

    ``period`` is the first day of the month (``YYYY-MM-01``); ``sent`` is the
    count of WhatsApp messages dispatched that month. Plain ``id`` PK — this is a
    counter, not a domain object.
    """

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="whatsapp_usage")
    period = models.DateField()  # first of the month
    sent = models.IntegerField(default=0)

    objects = TenantManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "period"], name="uniq_merchant_wa_period")
        ]
        indexes = [models.Index(fields=["merchant", "period"])]

    def __str__(self) -> str:
        return f"{self.merchant_id} · {self.period:%Y-%m} · {self.sent}"


def current_period() -> date:
    """First day of the current month (the active metering window)."""
    return timezone.localdate().replace(day=1)
