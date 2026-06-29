"""Messaging enums (Phase 1.7) — channels, statuses, automation keys.

Wire values mirror the contract (``Campaign.channel``, ``Automation.key``):
``PUSH|WHATSAPP|BOTH`` for channels, the five automation keys for triggers.
"""

from __future__ import annotations

from django.db import models


class MessageChannel(models.TextChoices):
    PUSH = "PUSH", "Push"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    BOTH = "BOTH", "Both"


class CampaignStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SCHEDULED = "scheduled", "Scheduled"
    SENDING = "sending", "Sending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


class AutomationKey(models.TextChoices):
    REWARD_READY = "reward_ready", "Reward ready"
    EXPIRY = "expiry", "Expiry"
    BIRTHDAY = "birthday", "Birthday"
    WINBACK = "winback", "Winback"
    WELCOME = "welcome", "Welcome"
