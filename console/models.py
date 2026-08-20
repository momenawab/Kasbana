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

from console import crm
from console.enums import AdminRole
from core.models import Merchant, TimeStampedModel, UUIDModel


class AdminUser(UUIDModel, TimeStampedModel):
    """A Stampn platform operator. Standalone identity (no merchant linkage)."""

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120, blank=True)
    password = models.CharField(max_length=128)  # Django-hashed
    role = models.CharField(max_length=20, choices=AdminRole.choices, default=AdminRole.READ_ONLY)
    is_active = models.BooleanField(default=True)
    # MFA (TOTP) — enrolled + enforced in Phase 15. ``mfa_secret`` is the base32
    # TOTP seed; ``mfa_enabled`` flips true only after a code is verified.
    mfa_secret = models.CharField(max_length=64, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    last_login_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    # Brute-force lockout (Phase 15): consecutive password failures + a lock window.
    failed_login_count = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

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


class AdminSession(UUIDModel, TimeStampedModel):
    """One admin login session (Phase 15) — the backing for device/session list,
    "log out everywhere", refresh rotation, and step-up re-auth.

    The session ``id`` is the ``sid`` embedded in the admin's access + refresh
    tokens. Every authenticated request checks the session is still active, so
    revoking a row kills its tokens immediately. ``refresh_epoch`` increments on
    each refresh so a replayed (stolen) refresh token is detected and the session
    is revoked. ``last_auth_at`` timestamps the last full credential proof (login
    or step-up), which sensitive actions require to be recent.
    """

    admin = models.ForeignKey(AdminUser, on_delete=models.CASCADE, related_name="sessions")
    refresh_epoch = models.IntegerField(default=0)  # rotation / reuse-detection counter
    user_agent = models.CharField(max_length=256, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_auth_at = models.DateTimeField(null=True, blank=True)  # login / step-up proof
    revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["admin", "revoked", "-created_at"])]

    def __str__(self) -> str:
        return f"session({self.admin_id}) {'revoked' if self.revoked else 'active'}"


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


class RetentionPolicy(UUIDModel, TimeStampedModel):
    """Platform-wide data-retention policy (Phase 13, PDPL).

    A single global row — read/written through ``current()``. Phase 13 *stores*
    and surfaces the policy; automatic enforcement (purging data past these
    windows) is deferred to a later phase — exactly like MFA in Phase 12, which
    is declared here and enforced later. A window of ``0`` means "keep
    indefinitely" (no automatic purge), which is the safe default.
    """

    # Retention windows in days; 0 = keep indefinitely.
    inactive_customer_days = models.IntegerField(default=0)  # cards with no activity
    closed_merchant_days = models.IntegerField(default=0)  # churned/closed merchant data
    audit_log_days = models.IntegerField(default=0)  # admin audit trail
    notes = models.TextField(blank=True)
    # Who last saved the policy (denormalised email survives an admin delete).
    updated_by = models.ForeignKey(
        AdminUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    updated_by_email = models.EmailField(blank=True)

    class Meta:
        verbose_name_plural = "retention policies"

    @classmethod
    def current(cls) -> RetentionPolicy:
        """The one global policy row, created lazily with safe defaults."""
        return cls.objects.first() or cls.objects.create()

    def __str__(self) -> str:
        return (
            f"RetentionPolicy(inactive={self.inactive_customer_days}d, "
            f"audit={self.audit_log_days}d)"
        )


class FeatureFlag(UUIDModel, TimeStampedModel):
    """A platform feature toggle (Phase 14) — flip behaviour without a deploy.

    ``enabled`` is the global default; per-merchant exceptions live in
    ``FeatureFlagOverride``. Runtime reads the resolved value via
    ``console.flags.flag_enabled(key, merchant)`` (a lazy import, so low-level
    apps don't take a load-time dependency on the console).
    """

    key = models.SlugField(max_length=64, unique=True)  # e.g. "whatsapp_channel"
    label = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=False)
    updated_by_email = models.EmailField(blank=True)

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.key}={'on' if self.enabled else 'off'}"


class FeatureFlagOverride(UUIDModel, TimeStampedModel):
    """A per-merchant override of a ``FeatureFlag``'s global default."""

    flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name="overrides")
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="feature_flag_overrides"
    )
    enabled = models.BooleanField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["flag", "merchant"], name="uniq_flag_merchant")
        ]

    def __str__(self) -> str:
        return f"{self.flag.key}[{self.merchant_id}]={'on' if self.enabled else 'off'}"


class PlatformSetting(UUIDModel, TimeStampedModel):
    """Global key/value config (Phase 14). ``value`` is JSON. Well-known keys:
    ``maintenance_mode`` -> ``{"enabled": bool, "message": str}`` (enforced by
    ``common.middleware.MaintenanceModeMiddleware``)."""

    key = models.SlugField(max_length=64, unique=True)
    value = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    updated_by_email = models.EmailField(blank=True)

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return f"setting({self.key})"


class Lead(UUIDModel, TimeStampedModel):
    """A sales lead — the CRM's central record, from first contact to merchant.

    Two things create a lead and they differ *only* in provenance:

    * the public marketing "Get started" form (``console.public``) — anonymous,
      unattended, ``lead_type=WEBSITE`` / ``created_by_type=SYSTEM``; and
    * a sales user in the console — ``lead_type=MANUAL``, ``created_by`` set.

    From there both follow one pipeline. No merchant linkage until it converts:
    a lead exists *before* signup, and ``converted_merchant`` is what closes
    that gap (see the Convert-To-Merchant flow).

    The CRM fields are stored as *slugs*, not FKs to ``CrmChoice``. That is
    deliberate: the vocabulary in ``console.crm`` is the system's, and a lead's
    history must not change meaning because an admin renamed or removed a
    dropdown row afterwards. ``CrmChoice`` decorates these slugs for display; it
    does not own them.
    """

    # ── Business information ─────────────────────────────────────────────────
    business_name = models.CharField(max_length=160)
    name = models.CharField(max_length=120)  # the owner / person we talk to
    phone = models.CharField(max_length=40)
    whatsapp = models.CharField(max_length=40, blank=True)
    # Blank-able since a manual lead is often just a name and a phone number
    # walked in off the street. The *public* form still requires it — that rule
    # lives in ``LeadCreateSerializer``, not here.
    email = models.EmailField(blank=True)
    instagram = models.CharField(max_length=120, blank=True)  # handle or URL
    facebook = models.CharField(max_length=200, blank=True)  # handle or URL
    website = models.URLField(blank=True)
    google_maps_url = models.URLField(max_length=500, blank=True)
    # Uploaded by Sales while qualifying (``POST /leads/{id}/logo``) and carried
    # onto ``Merchant.logo_url`` at conversion, so nobody re-uploads it. A URL
    # rather than a FileField to match Merchant.logo_url exactly — the upload
    # endpoint stores the file and hands back its URL (see ``common.uploads``).
    logo_url = models.URLField(max_length=500, blank=True)
    area = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=64, blank=True)  # CrmChoice(CATEGORY) slug
    address = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    # ── Provenance ───────────────────────────────────────────────────────────
    lead_type = models.CharField(
        max_length=16, choices=crm.LeadType.choices, default=crm.LeadType.MANUAL
    )
    source = models.CharField(
        max_length=32, choices=crm.LeadSource.choices, default=crm.LeadSource.MANUAL
    )
    created_by_type = models.CharField(
        max_length=16, choices=crm.LeadCreatedBy.choices, default=crm.LeadCreatedBy.SYSTEM
    )
    # Null for website leads (nobody created them) and for leads whose creator
    # has since been deleted — the admin team churns, the pipeline outlives it.
    created_by = models.ForeignKey(
        "console.AdminUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads_created",
    )

    # ── CRM state ────────────────────────────────────────────────────────────
    assigned_sales = models.ForeignKey(
        "console.AdminUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads_assigned",
    )
    status = models.CharField(
        max_length=32, choices=crm.LeadStatus.choices, default=crm.LeadStatus.NEW_LEAD
    )
    priority = models.CharField(
        max_length=16, choices=crm.LeadPriority.choices, default=crm.LeadPriority.MEDIUM
    )
    temperature = models.CharField(
        max_length=16, choices=crm.LeadTemperature.choices, default=crm.LeadTemperature.WARM
    )
    lead_score = models.PositiveSmallIntegerField(default=0)
    expected_plan = models.CharField(max_length=32, blank=True)
    expected_revenue = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    contact_method = models.CharField(max_length=32, blank=True)
    next_action = models.CharField(max_length=32, blank=True)
    last_activity = models.CharField(max_length=200, blank=True)  # display summary
    last_contact_at = models.DateTimeField(null=True, blank=True)
    next_follow_up_at = models.DateTimeField(null=True, blank=True)
    contacted_at = models.DateTimeField(null=True, blank=True)

    # ── Conversion ───────────────────────────────────────────────────────────
    converted_merchant = models.ForeignKey(
        Merchant,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_leads",
    )
    converted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # The pipeline board and KPI cards slice by these.
            models.Index(fields=["status"]),
            models.Index(fields=["lead_type"]),
            models.Index(fields=["assigned_sales", "status"]),
            # Today's / overdue follow-ups — the query behind the notifications.
            models.Index(fields=["next_follow_up_at"]),
            # Duplicate detection probes phone and email on every manual create.
            models.Index(fields=["phone"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self) -> str:
        return f"lead({self.business_name} · {self.phone})"

    @property
    def is_converted(self) -> bool:
        return self.converted_merchant_id is not None

    def recalculate_score(self, *, save: bool = True) -> int:
        """Recompute and persist ``lead_score``. Safe to call after any mutation
        — ``crm.score_lead`` derives the score from scratch every time."""
        self.lead_score = crm.score_lead(self)
        if save and self.pk:
            self.save(update_fields=["lead_score", "updated_at"])
        return self.lead_score


class LeadActivity(UUIDModel, TimeStampedModel):
    """One entry on a lead's timeline — the CRM's audit trail, in sales language.

    Distinct from ``AdminAuditLog``: that one answers "which operator touched
    what" for compliance and covers the whole console. This one is the story of
    a *lead*, written for the sales user reading it, and includes things no
    admin did at all (the website form submitting itself).

    Rows are append-only. ``actor_label`` snapshots the actor's name at write
    time so the timeline still reads correctly after an admin leaves and the FK
    nulls out.
    """

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    kind = models.CharField(max_length=32, choices=crm.ActivityKind.choices)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    actor = models.ForeignKey(
        "console.AdminUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_activities",
    )
    actor_label = models.CharField(max_length=120, blank=True)  # "System" when unattended

    class Meta:
        ordering = ["-created_at"]  # newest first — the timeline's reading order
        indexes = [models.Index(fields=["lead", "-created_at"])]

    def __str__(self) -> str:
        return f"activity({self.kind} · {self.lead_id})"


class LeadCall(UUIDModel, TimeStampedModel):
    """One logged call against a lead.

    Immutable history: a call records what happened at a moment, so editing the
    lead's status later never rewrites it. Logging a call also writes a
    ``PHONE_CALL_LOGGED`` activity and bumps the lead's score (calls are a
    scoring signal) — that orchestration lives in the view, not here.
    """

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="calls")
    called_at = models.DateTimeField()
    duration_seconds = models.PositiveIntegerField(default=0)
    result = models.CharField(max_length=32, choices=crm.CallResult.choices)
    contact_method = models.CharField(
        max_length=32, choices=crm.ContactMethod.choices, default=crm.ContactMethod.PHONE
    )
    next_follow_up_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    logged_by = models.ForeignKey(
        "console.AdminUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_calls",
    )
    logged_by_label = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-called_at"]
        indexes = [models.Index(fields=["lead", "-called_at"])]

    def __str__(self) -> str:
        return f"call({self.lead_id} · {self.result})"


class CrmChoice(UUIDModel, TimeStampedModel):
    """One row in a configurable CRM dropdown (Settings → CRM Configuration).

    This table is an *overlay*, not the source of truth. For every kind in
    ``crm.SYSTEM_CHOICES`` the code's enum defines which values exist; a row
    here with ``is_system=True`` carries that value's label, colour and order,
    and admins may edit those three freely. What they may not do is delete it or
    change its slug — scoring, conversion and the KPI cards read those slugs by
    name, so removing one would break the maths silently rather than loudly.

    Admins may also add rows with ``is_system=False``: extra statuses, sources,
    or plans that carry no logic and are pure vocabulary. Business categories
    have no enum at all, so every category row is one of these.

    ``console.management`` seeds the system rows; ``ensure_seeded`` keeps them
    in step when a later release adds an enum value.
    """

    kind = models.CharField(max_length=32, choices=crm.CrmChoiceKind.choices)
    slug = models.SlugField(max_length=64)
    label = models.CharField(max_length=120)
    color = models.CharField(max_length=16, blank=True)  # hex, for the status badge
    order = models.PositiveSmallIntegerField(default=0)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)  # hide from pickers, keep history readable

    class Meta:
        ordering = ["kind", "order", "label"]
        constraints = [
            models.UniqueConstraint(fields=["kind", "slug"], name="crmchoice_unique_kind_slug"),
        ]
        indexes = [models.Index(fields=["kind", "is_active"])]

    def __str__(self) -> str:
        return f"crm_choice({self.kind}.{self.slug})"


class ContactMessage(UUIDModel, TimeStampedModel):
    """An inbound support/contact message.

    Two sources feed one queue: the public marketing "Let's talk" form (anonymous,
    ``source=marketing``, ``merchant`` null) and a logged-in merchant's dashboard
    support form (``source=dashboard``, ``merchant`` set). The team works both from
    the admin console — the global Messages inbox and, for dashboard messages, the
    merchant's Support tab. Kept separate from ``Lead`` because a contact message
    is a support enquiry, not a sales lead.
    """

    class Status(models.TextChoices):
        NEW = "new", "New"
        READ = "read", "Read"
        REPLIED = "replied", "Replied"

    class Source(models.TextChoices):
        MARKETING = "marketing", "Marketing site"
        DASHBOARD = "dashboard", "Merchant dashboard"

    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)
    # Dashboard messages carry the sending merchant so they surface on its Support
    # tab. SET_NULL (not CASCADE): deleting a merchant must not erase the support
    # history the team may still need. Marketing messages leave this null.
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MARKETING)
    merchant = models.ForeignKey(
        "core.Merchant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contact_messages",
    )
    read_at = models.DateTimeField(null=True, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"message({self.subject} · {self.email})"
