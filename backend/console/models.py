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


class ContentFlag(models.Model):
    """A flagged piece of merchant content for moderation review (Phase 9).

    Raised by a heuristic scan or a report; a Support+ admin approves (content is
    fine → dismiss) or rejects (content violates). One row per (target, reason)
    while pending, so a re-scan doesn't pile up duplicates.
    """

    class TargetType(models.TextChoices):
        CARD = "card", "Card"
        MERCHANT = "merchant", "Merchant"

    class Source(models.TextChoices):
        HEURISTIC = "heuristic", "Heuristic scan"
        REPORT = "report", "Report"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"  # reviewed, content is fine
        REJECTED = "rejected", "Rejected"  # reviewed, content violates

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="content_flags")
    target_type = models.CharField(max_length=16, choices=TargetType.choices)
    target_id = models.CharField(max_length=64)  # card id, or merchant id
    label = models.CharField(max_length=200, blank=True)  # snapshot of the flagged text
    reason = models.CharField(max_length=200)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.HEURISTIC)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    resolved_by = models.ForeignKey(
        AdminUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_flags"
    )
    resolution_notes = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # A given target can only have one PENDING flag for the same reason —
            # keeps a repeated heuristic scan idempotent.
            models.UniqueConstraint(
                fields=["target_type", "target_id", "reason"],
                condition=models.Q(status="pending"),
                name="uniq_pending_content_flag",
            )
        ]

    def __str__(self) -> str:
        return f"{self.target_type}:{self.target_id} · {self.reason} ({self.status})"


class Announcement(models.Model):
    """A platform broadcast to a merchant segment (Phase 10).

    Delivered in-app (a per-merchant ``AnnouncementDelivery`` row the dashboard
    reads) and/or by email. ``recipients``/``emails_sent`` are snapshotted at
    send; opens are derived from ``AnnouncementDelivery.read_at``.
    """

    class Channel(models.TextChoices):
        IN_APP = "in_app", "In-app"
        EMAIL = "email", "Email"
        BOTH = "both", "In-app + email"

    class Segment(models.TextChoices):
        ALL = "all", "All merchants"
        PLAN = "plan", "By plan"
        TRIAL_ENDING = "trial_ending", "Trial ending"
        AT_RISK = "at_risk", "At-risk"
        ACTIVE = "active", "Recently active"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        SENT = "sent", "Sent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=160)
    body = models.TextField()
    channel = models.CharField(max_length=8, choices=Channel.choices, default=Channel.IN_APP)
    audience = models.CharField(max_length=16, choices=Segment.choices, default=Segment.ALL)
    audience_param = models.CharField(max_length=32, blank=True)  # e.g. plan key for PLAN
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    schedule_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    recipients = models.IntegerField(default=0)  # audience size at send
    emails_sent = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        AdminUser, on_delete=models.SET_NULL, null=True, related_name="announcements"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.title} → {self.audience} ({self.status})"


class AnnouncementDelivery(models.Model):
    """One in-app delivery of an announcement to a merchant; ``read_at`` powers
    the dashboard's unread state + the open-rate stat."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.ForeignKey(
        Announcement, on_delete=models.CASCADE, related_name="deliveries"
    )
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="announcement_deliveries"
    )
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["announcement", "merchant"], name="uniq_announcement_merchant"
            )
        ]

    def __str__(self) -> str:
        return f"{self.announcement_id} → {self.merchant_id}"


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
