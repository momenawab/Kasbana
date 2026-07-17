# core/enums.py — IMPORT FROM HERE. NEVER REDEFINE THESE VALUES.
# Frozen in Phase 1.0 (contract §3.2). Any change is a joint PR to the contract.
from django.db import models


class Role(models.TextChoices):
    OWNER = "OWNER", "Owner"
    ADMIN = "ADMIN", "Admin"
    # Lateral specialised roles (added post-1.0; additive — existing values
    # unchanged). DESIGNER owns cards/branding, MARKETING owns engagement.
    MARKETING = "MARKETING", "Marketing"
    DESIGNER = "DESIGNER", "Designer"
    SCANNER = "SCANNER", "Scanner"


class MerchantStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"


class PlanTier(models.TextChoices):
    FREE = "FREE", "Free"
    STARTER = "STARTER", "Starter"
    GROWTH = "GROWTH", "Growth"
    CHAIN = "CHAIN", "Chain"
    # Negotiated tier (added post-1.0; additive — existing values unchanged,
    # same precedent as Role gaining MARKETING/DESIGNER). It names the *tier*
    # only: which negotiated plan a merchant is on lives in
    # ``Subscription.enterprise_plan``, an FK to the billing.Plan row that
    # carries the agreed name, price and limits.
    ENTERPRISE = "ENTERPRISE", "Enterprise"


class CardType(models.TextChoices):
    STAMP = "STAMP", "Stamp card"
    POINTS = "POINTS", "Points card"


class CardStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    ARCHIVED = "ARCHIVED", "Archived"


class CustomerCardStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    COMPLETED = "COMPLETED", "Completed"
    BLOCKED = "BLOCKED", "Blocked"


class LedgerEvent(models.TextChoices):
    ENROLL = "ENROLL", "Enrollment"
    STAMP = "STAMP", "Stamp added"
    REDEEM = "REDEEM", "Reward redeemed"
    ADJUST = "ADJUST", "Manual adjustment"


class WalletPlatform(models.TextChoices):
    APPLE = "APPLE", "Apple Wallet"
    GOOGLE = "GOOGLE", "Google Wallet"


class RedemptionStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    CLAIMED = "CLAIMED", "Claimed"
    VOID = "VOID", "Void"
