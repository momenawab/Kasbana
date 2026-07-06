"""Account-lifecycle models (Phase 1.5) — invites, password resets, settings.

Owned by ``accounts/`` so the frozen ``core`` schema is untouched.
``MerchantSettings`` holds the contact / locale / notification fields the
contract's settings endpoints need that aren't on ``core.Merchant``.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.enums import Role
from core.models import Location, Merchant, TimeStampedModel, UUIDModel

INVITE_TTL_DAYS = 7
RESET_TTL_HOURS = 1


def _token() -> str:
    return secrets.token_urlsafe(32)


def _invite_expiry() -> datetime:
    return timezone.now() + timedelta(days=INVITE_TTL_DAYS)


def _reset_expiry() -> datetime:
    return timezone.now() + timedelta(hours=RESET_TTL_HOURS)


class StaffInvite(UUIDModel):
    """A pending staff invite; accepted at ``POST /auth/invite/{t}``."""

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="staff_invites")
    email = models.EmailField()
    role = models.CharField(max_length=16, choices=Role.choices)
    location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="staff_invites"
    )
    token = models.CharField(max_length=64, unique=True, default=_token)
    expires_at = models.DateTimeField(default=_invite_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self) -> bool:
        return self.accepted_at is None and self.expires_at > timezone.now()

    def __str__(self) -> str:
        return f"{self.email} -> {self.merchant_id} ({self.role})"


class PasswordResetToken(UUIDModel):
    """Single-use password-reset token issued by ``POST /auth/forgot``."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="password_reset_tokens"
    )
    token = models.CharField(max_length=64, unique=True, default=_token)
    expires_at = models.DateTimeField(default=_reset_expiry)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


class MerchantSettings(UUIDModel, TimeStampedModel):
    """Contact / locale / notification settings not present on ``core.Merchant``."""

    merchant = models.OneToOneField(Merchant, on_delete=models.CASCADE, related_name="settings")
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    # Pass-back contact + social links — each optional; only the ones the merchant
    # fills in appear on the wallet pass back (Apple backFields / Google links).
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    tiktok_url = models.URLField(blank=True)
    whatsapp = models.CharField(max_length=32, blank=True)  # number -> wa.me link
    terms_url = models.URLField(blank=True)
    branches = models.TextField(blank=True)  # optional free text (one branch per line)
    language = models.CharField(max_length=2, choices=[("ar", "ar"), ("en", "en")], default="ar")
    notif_email = models.BooleanField(default=True)
    notif_whatsapp = models.BooleanField(default=False)
    # Branded enrollment page (custom_branding capability): custom welcome copy
    # shown on the public join page. Blank falls back to a default headline.
    enroll_headline = models.CharField(max_length=80, blank=True)
    enroll_tagline = models.CharField(max_length=160, blank=True)

    def __str__(self) -> str:
        return f"settings({self.merchant_id})"
