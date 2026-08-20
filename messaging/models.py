"""Messaging models (Phase 1.7) — campaigns + automations.

A ``messaging/`` app (queue ``messaging`` already configured). Both models are
tenant-scoped via a ``merchant`` FK and use the shared ``TenantManager`` so every
queryset goes through ``for_merchant``. Delivery rides the free wallet push
channel (Apple ``changeMessage`` + Google ``addMessage``).
"""

from __future__ import annotations

from django.db import models

from core.models import Merchant, TimeStampedModel, UUIDModel
from core.tenancy import TenantManager
from messaging.enums import AutomationKey, CampaignStatus


class Campaign(UUIDModel, TimeStampedModel):
    """A one-shot broadcast to a computed audience (segment key)."""

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="campaigns")
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
        return f"{self.audience} ({self.status})"


class Automation(UUIDModel, TimeStampedModel):
    """A per-merchant lifecycle trigger; one row per ``AutomationKey``."""

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="automations")
    key = models.CharField(max_length=24, choices=AutomationKey.choices)
    enabled = models.BooleanField(default=False)
    timing = models.CharField(max_length=64, blank=True)  # free-form (e.g. "+7d")
    template = models.TextField(blank=True)

    objects = TenantManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "key"], name="uniq_merchant_automation_key")
        ]

    def __str__(self) -> str:
        return f"{self.merchant_id} · {self.key} ({'on' if self.enabled else 'off'})"
