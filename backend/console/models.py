"""Platform-admin models — a standalone auth boundary + audit spine.

``AdminUser`` is deliberately NOT the merchant ``django.contrib.auth.User`` nor a
``StaffUser`` — it is a separate identity for Stampn employees so a merchant token
can never authenticate an admin endpoint (see ``console.auth``). Passwords use
Django's hashers; JWTs are minted in ``console.auth`` with an ``aud:"admin"`` claim.

``AdminAuditLog`` records every mutating admin action (and sensitive reads like
impersonation / PII export). The viewer UI lands in Phase 13; the spine is built
here so every later phase can just call ``console.audit.record()``.
"""

from __future__ import annotations

import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models

from console.enums import AdminRole
from core.models import Merchant, TimeStampedModel, UUIDModel


class AdminUser(UUIDModel, TimeStampedModel):
    """A Stampn platform operator. Standalone identity (no merchant linkage)."""

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120, blank=True)
    password = models.CharField(max_length=128)  # Django-hashed
    role = models.CharField(max_length=20, choices=AdminRole.choices, default=AdminRole.READ_ONLY)
    is_active = models.BooleanField(default=True)
    # MFA scaffold — populated/enforced in Phase 15.
    mfa_secret = models.CharField(max_length=64, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    last_login_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return f"{self.email} ({self.role})"

    # ── auth helpers ──────────────────────────────────────────────────────────
    def set_password(self, raw: str) -> None:
        self.password = make_password(raw)

    def check_password(self, raw: str) -> bool:
        return check_password(raw, self.password)

    @property
    def is_super_admin(self) -> bool:
        return self.role == AdminRole.SUPER_ADMIN

    # DRF's request.user contract — an authenticated AdminUser reads as logged-in
    # without being a Django auth user.
    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False


class MerchantAdminMeta(UUIDModel, TimeStampedModel):
    """Admin-only metadata about a merchant — kept OUT of the frozen ``core``
    contract. One row per merchant, created lazily by the console when first
    edited. Holds internal notes, ops flags, and the assigned account manager.
    """

    merchant = models.OneToOneField(Merchant, on_delete=models.CASCADE, related_name="admin_meta")
    internal_notes = models.TextField(blank=True)
    flags = models.JSONField(default=dict, blank=True)  # e.g. {"vip": true, "watch": true}
    account_manager = models.ForeignKey(
        AdminUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_merchants",
    )

    def __str__(self) -> str:
        return f"admin_meta({self.merchant_id})"


class Impersonation(models.Model):
    """One admin view-as-merchant session (Phase 6) — the sharpest support tool.

    The impersonation token is a short-lived *merchant* access token carrying
    ``impersonation_id``; the merchant auth layer (``common.auth``) checks this
    row on every request so an admin-side "end" kills the session before its
    JWT expiry. Time-limited, fully audited, and blocked from billing actions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(
        AdminUser, on_delete=models.SET_NULL, null=True, related_name="impersonations"
    )
    admin_email = models.EmailField(blank=True)  # snapshot (survives admin delete)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="impersonations")
    target_email = models.EmailField(blank=True)  # the staff identity impersonated
    reason = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.admin_email} as {self.merchant_id} until {self.expires_at:%H:%M}"

    def is_active(self) -> bool:
        from django.utils import timezone

        return self.ended_at is None and self.expires_at > timezone.now()


class SupportNote(models.Model):
    """A support-thread note on a merchant (Phase 6). Append-only in practice."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="support_notes")
    admin = models.ForeignKey(
        AdminUser, on_delete=models.SET_NULL, null=True, related_name="support_notes"
    )
    admin_email = models.EmailField(blank=True)  # snapshot (survives admin delete)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"note({self.merchant_id}) by {self.admin_email}"


class AdminAuditLog(models.Model):
    """One admin action. Append-only; never edited or deleted in normal operation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        AdminUser, on_delete=models.SET_NULL, null=True, related_name="audit_events"
    )
    actor_email = models.EmailField(blank=True)  # denormalised snapshot (survives actor delete)
    action = models.CharField(max_length=64)  # e.g. "merchant.suspend", "invoice.refund"
    target_type = models.CharField(max_length=48, blank=True)  # e.g. "merchant", "invoice"
    target_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)  # before/after, reason, amounts…
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=256, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.actor_email} · {self.action} · {self.created_at:%Y-%m-%d %H:%M}"
