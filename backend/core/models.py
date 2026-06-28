"""Kasbana data model — every persistent model lives here (contract §3.4).

FROZEN in Phase 1.0. FK attribute names are fixed; the DB column is
``<attr>_id``. All models have a UUIDv4 primary key. After the ``core-v1`` tag,
schema changes require a joint PR to the contract first.
"""

from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from core import constants, enums
from core.tenancy import TenantManager


def _generate_auth_token() -> str:
    """Per-pass secret used for Apple web-service auth (48 hex chars)."""
    return secrets.token_hex(constants.AUTH_TOKEN_BYTES)


# ── Abstract bases ────────────────────────────────────────────────────────────
class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ── Tenant root ───────────────────────────────────────────────────────────────
class Merchant(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    legal_name = models.CharField(max_length=160, blank=True)
    status = models.CharField(
        max_length=16, choices=enums.MerchantStatus.choices, default=enums.MerchantStatus.ACTIVE
    )
    plan = models.CharField(
        max_length=16, choices=enums.PlanTier.choices, default=enums.PlanTier.FREE
    )
    logo_url = models.URLField(blank=True)
    color_bg = models.CharField(max_length=7, blank=True)  # hex #RRGGBB
    color_fg = models.CharField(max_length=7, blank=True)  # hex #RRGGBB

    def __str__(self) -> str:
        return self.name


class Location(UUIDModel, TimeStampedModel):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="locations")
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=255, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)

    objects = TenantManager()

    def __str__(self) -> str:
        return self.name


class StaffUser(UUIDModel):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="staff")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile"
    )
    role = models.CharField(max_length=16, choices=enums.Role.choices)
    location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="staff"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    def __str__(self) -> str:
        return f"{self.user} @ {self.merchant} ({self.role})"


class Card(UUIDModel, TimeStampedModel):
    """Program template."""

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="cards")
    type = models.CharField(
        max_length=16, choices=enums.CardType.choices, default=enums.CardType.STAMP
    )
    name = models.CharField(max_length=120)
    stamps_required = models.IntegerField()
    reward_title = models.CharField(max_length=120)
    reward_description = models.TextField(blank=True)
    color_bg = models.CharField(max_length=7, blank=True)
    color_fg = models.CharField(max_length=7, blank=True)
    logo_url = models.URLField(blank=True)
    google_class_id = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=16, choices=enums.CardStatus.choices, default=enums.CardStatus.DRAFT
    )

    objects = TenantManager()

    def __str__(self) -> str:
        return self.name


class CustomerCard(UUIDModel, TimeStampedModel):
    """Per-customer instance — ``id`` is the wallet serialNumber."""

    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="customer_cards")
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="customer_cards"
    )  # denormalized for scoping
    customer_phone = models.CharField(max_length=20)  # E.164
    customer_name = models.CharField(max_length=120, blank=True)
    stamp_count = models.IntegerField(default=0)  # cached balance, derived from ledger
    auth_token = models.CharField(max_length=48, default=_generate_auth_token)
    status = models.CharField(
        max_length=16,
        choices=enums.CustomerCardStatus.choices,
        default=enums.CustomerCardStatus.ACTIVE,
    )
    consent_at = models.DateTimeField(null=True, blank=True)  # PDPL consent timestamp
    enrolled_at = models.DateTimeField(default=timezone.now)
    last_event_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["card", "customer_phone"], name="uniq_card_customer_phone"
            )
        ]

    def __str__(self) -> str:
        return f"{self.customer_phone} · {self.card}"


class StampLedger(UUIDModel):
    """Append-only — never updated or deleted."""

    customer_card = models.ForeignKey(
        CustomerCard, on_delete=models.CASCADE, related_name="ledger_entries"
    )
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="ledger_entries")
    event_type = models.CharField(max_length=16, choices=enums.LedgerEvent.choices)
    delta = models.IntegerField()
    balance_after = models.IntegerField()
    staff = models.ForeignKey(
        StaffUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="ledger_entries"
    )
    location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="ledger_entries"
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    class Meta:
        indexes = [
            models.Index(fields=["customer_card", "created_at"]),
            models.Index(fields=["staff", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} {self.delta:+d} -> {self.balance_after}"


class Reward(UUIDModel):
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="rewards")
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    threshold = models.IntegerField()  # stamps required to unlock
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title


class Redemption(UUIDModel):
    customer_card = models.ForeignKey(
        CustomerCard, on_delete=models.CASCADE, related_name="redemptions"
    )
    reward = models.ForeignKey(Reward, on_delete=models.PROTECT, related_name="redemptions")
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="redemptions")
    staff = models.ForeignKey(
        StaffUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="redemptions"
    )
    location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="redemptions"
    )
    status = models.CharField(
        max_length=16,
        choices=enums.RedemptionStatus.choices,
        default=enums.RedemptionStatus.CLAIMED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    def __str__(self) -> str:
        return f"{self.reward} ({self.status})"


class EnrollmentToken(UUIDModel):
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="enrollment_tokens"
    )
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="enrollment_tokens")
    token = models.CharField(max_length=32, unique=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    def __str__(self) -> str:
        return self.token


class WalletRegistration(UUIDModel, TimeStampedModel):
    customer_card = models.ForeignKey(
        CustomerCard, on_delete=models.CASCADE, related_name="wallet_registrations"
    )
    platform = models.CharField(max_length=16, choices=enums.WalletPlatform.choices)
    device_library_id = models.CharField(max_length=64, blank=True)  # Apple device id
    push_token = models.CharField(max_length=255, blank=True)  # Apple APNs token
    google_object_id = models.CharField(max_length=120, blank=True)  # Google object ref
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["customer_card", "platform"]),
            models.Index(fields=["device_library_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.platform} · {self.customer_card_id}"
