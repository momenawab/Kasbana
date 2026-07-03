"""Registration-page theme + QR style (Phase 1 · finalize-phases).

Owned by ``branding/`` so the frozen ``core`` schema is untouched. One row per
merchant is the **default** (``card`` is null); an optional per-card row
**overrides** it for that program. Resolution + entitlement gating live in
``branding.services``.
"""

from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models

from branding.defaults import default_fields_config, default_qr_style
from core.models import Card, Merchant, TimeStampedModel, UUIDModel
from core.tenancy import TenantManager

# Matches the ``#RRGGBB`` shape used by ``core.Merchant``/``Card`` colors.
hex_color = RegexValidator(r"^#(?:[0-9a-fA-F]{6})$", "Enter a hex color like #1A2B3C.")


class RegistrationTheme(UUIDModel, TimeStampedModel):
    """Brandable look of the public join page + its QR, per merchant (+card)."""

    TEMPLATE_CHOICES = [(k, k) for k in ("classic", "hero", "minimal", "bold")]
    FONT_CHOICES = [(k, k) for k in ("system", "serif", "rounded")]

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="enroll_themes")
    # Null = the merchant-wide default. A row with a card overrides it for that
    # program only (resolution falls back default -> system default).
    card = models.ForeignKey(
        Card, on_delete=models.CASCADE, null=True, blank=True, related_name="enroll_themes"
    )

    # Page theme
    template_key = models.CharField(max_length=16, choices=TEMPLATE_CHOICES, default="classic")
    cover_image_url = models.URLField(blank=True)  # uploaded via the shared /uploads endpoint
    bg_color = models.CharField(max_length=7, blank=True, validators=[hex_color])
    accent_color = models.CharField(max_length=7, blank=True, validators=[hex_color])
    button_text_color = models.CharField(max_length=7, blank=True, validators=[hex_color])
    font = models.CharField(max_length=16, choices=FONT_CHOICES, default="system")
    welcome_body = models.TextField(max_length=600, blank=True)

    # Which optional fields to collect (name/email/birthday show+required).
    fields_config = models.JSONField(default=default_fields_config)
    # QR look: module_style / fg_color / bg_color / frame.
    qr_style = models.JSONField(default=default_qr_style)

    terms_url = models.URLField(blank=True)
    privacy_url = models.URLField(blank=True)
    # Honoured only on custom_branding plans (white-label by default); free plans
    # always show the footer regardless (gating forces it in resolve_theme).
    hide_powered_by = models.BooleanField(default=True)

    objects = TenantManager()

    class Meta:
        constraints = [
            # Exactly one merchant-wide default (card is null)...
            models.UniqueConstraint(
                fields=["merchant"],
                condition=models.Q(card__isnull=True),
                name="uniq_merchant_default_theme",
            ),
            # ...and at most one override per card.
            models.UniqueConstraint(
                fields=["merchant", "card"],
                name="uniq_merchant_card_theme",
            ),
        ]

    def __str__(self) -> str:
        return f"theme({self.merchant_id}, card={self.card_id})"
