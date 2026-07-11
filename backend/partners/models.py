"""Partner / merchant-referral program models (Phase E.1).

A **partner is an existing merchant** who refers new merchants via a code. When a
referred merchant first converts to paid, both the partner and the new merchant
receive free subscription months (comp) — one-time, amounts + on/off configured
in the admin panel (a global default with optional per-partner overrides).

``core`` is frozen, so all state lives here: a ``Partner`` row hangs off a
``core.Merchant`` (OneToOne), never a column on ``Merchant`` itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import models

from core.models import Merchant, TimeStampedModel, UUIDModel


@dataclass(frozen=True)
class RewardConfig:
    """The resolved reward settings for a partner (override → global default)."""

    enabled: bool
    partner_free_months: int
    merchant_free_months: int


class PartnerProgramConfig(UUIDModel, TimeStampedModel):
    """Platform-wide default for the referral program (a single row).

    ``enabled`` defaults to ``False`` so the program is off until an admin turns
    it on. Per-partner overrides on ``Partner`` win over these values.
    """

    enabled = models.BooleanField(default=False)
    partner_free_months = models.PositiveIntegerField(default=1)
    merchant_free_months = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "partner program config"

    def __str__(self) -> str:
        return f"program(enabled={self.enabled})"

    @classmethod
    def get_solo(cls) -> PartnerProgramConfig:
        """The single global config row, created with defaults on first access."""
        obj, _ = cls.objects.get_or_create(pk=cls._solo_pk())
        return obj

    @staticmethod
    def _solo_pk() -> str:
        # A fixed sentinel UUID so there is always exactly one config row.
        return "00000000-0000-0000-0000-000000000001"


class Partner(UUIDModel, TimeStampedModel):
    """An existing merchant enrolled as a referrer, with a unique code.

    The three ``*_override`` fields are nullable: ``None`` means "fall back to the
    global :class:`PartnerProgramConfig`", a value overrides it for this partner.
    """

    merchant = models.OneToOneField(
        Merchant, on_delete=models.CASCADE, related_name="partner_profile"
    )
    code = models.CharField(max_length=32, unique=True, db_index=True)
    active = models.BooleanField(default=True)

    enabled_override = models.BooleanField(null=True, blank=True)
    partner_free_months_override = models.PositiveIntegerField(null=True, blank=True)
    merchant_free_months_override = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.code} ({self.merchant_id})"

    def resolved_config(self, program: PartnerProgramConfig | None = None) -> RewardConfig:
        """Merge this partner's overrides over the global default."""
        program = program or PartnerProgramConfig.get_solo()
        enabled = program.enabled if self.enabled_override is None else self.enabled_override
        return RewardConfig(
            enabled=bool(self.active and enabled),
            partner_free_months=(
                program.partner_free_months
                if self.partner_free_months_override is None
                else self.partner_free_months_override
            ),
            merchant_free_months=(
                program.merchant_free_months
                if self.merchant_free_months_override is None
                else self.merchant_free_months_override
            ),
        )


class PartnerReferral(UUIDModel, TimeStampedModel):
    """One referred merchant, attributed to one partner.

    ``referred_merchant`` is OneToOne — a merchant is referred by at most one
    partner. ``reward_granted`` guards the one-time grant so a repeated conversion
    webhook never double-pays.
    """

    class Source(models.TextChoices):
        SIGNUP_CODE = "signup_code", "Signup code"
        ADMIN = "admin", "Admin assignment"

    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name="referrals")
    referred_merchant = models.OneToOneField(
        Merchant, on_delete=models.CASCADE, related_name="referred_by"
    )
    attributed_via = models.CharField(max_length=16, choices=Source.choices)
    converted_at = models.DateTimeField(null=True, blank=True)
    reward_granted = models.BooleanField(default=False)
    partner_months_granted = models.PositiveIntegerField(default=0)
    merchant_months_granted = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["partner", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.partner_id} → {self.referred_merchant_id}"
