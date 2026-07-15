"""Messaging enums (Phase 1.7) — statuses, automation keys.

Wire values mirror the contract (``Automation.key``): the campaign statuses and
the five automation keys for triggers. Delivery is push-only (free wallet
channel), so there is no channel enum.
"""

from __future__ import annotations

from django.db import models


class CampaignStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SCHEDULED = "scheduled", "Scheduled"
    SENDING = "sending", "Sending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


class AutomationKey(models.TextChoices):
    REWARD_READY = "reward_ready", "Reward ready"
    ALMOST_THERE = "almost_there", "Almost there"
    EXPIRY = "expiry", "Expiry"
    BIRTHDAY = "birthday", "Birthday"
    WINBACK = "winback", "Winback"
    WELCOME = "welcome", "Welcome"
