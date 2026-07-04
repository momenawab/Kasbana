"""Wallet models — the per-card message ledger for free wallet push.

The wallet backends are otherwise stateless (they build passes on demand). This
one model persists the *latest message* shown on a customer's pass so the Apple
pass builder can render it as a back field with a ``changeMessage`` (which is
what makes iOS surface a lock-screen notification when it changes). Google reads
nothing from here — its ``addMessage`` API stores the message on Google's side —
but we record every send for both platforms for history/debugging.
"""

from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models

from core.enums import WalletPlatform
from core.models import Card, CustomerCard, Merchant, TimeStampedModel, UUIDModel
from core.tenancy import TenantManager

# Matches the ``#RRGGBB`` shape used by ``core.Merchant``/``Card`` colors.
hex_color = RegexValidator(r"^#(?:[0-9a-fA-F]{6})$", "Enter a hex color like #1A2B3C.")


class WalletMessage(UUIDModel, TimeStampedModel):
    """A push message sent to one customer's wallet pass (free channel).

    The newest row for a ``customer_card`` is the one the Apple pass surfaces;
    older rows are kept only as a sent-history trail.
    """

    customer_card = models.ForeignKey(
        CustomerCard, on_delete=models.CASCADE, related_name="wallet_messages"
    )
    title = models.CharField(max_length=120, blank=True)
    body = models.TextField()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["customer_card", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.customer_card_id}: {self.body[:32]}"


class CardShortCode(UUIDModel, TimeStampedModel):
    """A short, human-typeable code for one customer's pass (note 1).

    The wallet QR carries the opaque ``WLA<uuid-hex>`` payload, but the barcode
    ``altText`` printed under it is this short code — so a cashier can *type* it
    on the Scan screen instead of scanning. Generated lazily the first time a
    pass is built (see ``wallets.shortcode.code_for``); resolved back to the card
    (tenant-scoped) by the Scan endpoint. ``core.CustomerCard`` is a frozen
    contract model, so this lives here rather than as a field on it.
    """

    customer_card = models.OneToOneField(
        CustomerCard, on_delete=models.CASCADE, related_name="short_code"
    )
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="card_short_codes"
    )
    code = models.CharField(max_length=12, unique=True)

    class Meta:
        indexes = [models.Index(fields=["merchant", "code"])]

    def __str__(self) -> str:
        return self.code


class WalletSyncFailure(UUIDModel, TimeStampedModel):
    """A failed wallet provisioning/push operation (Phase 14 ops log).

    Recorded by the wallet tasks when a Google/Apple sync raises, so the ops
    console can surface it and re-provision (re-enqueue the task). ``resolved``
    flips when an admin re-provisions or the row is dismissed.
    """

    customer_card = models.ForeignKey(
        CustomerCard,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sync_failures",
    )
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="wallet_sync_failures"
    )
    platform = models.CharField(max_length=16, choices=WalletPlatform.choices, blank=True)
    operation = models.CharField(max_length=32)  # provision / push_update
    error = models.CharField(max_length=500, blank=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["resolved", "-created_at"]),
            models.Index(fields=["merchant", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.operation} {self.platform} · {self.customer_card_id} · {self.error[:40]}"


class WalletCardDesign(UUIDModel, TimeStampedModel):
    """Merchant-editable Apple/Google pass design for one card (notes 2-4).

    Owned by ``wallets/`` so the frozen ``core.Card`` schema is untouched. Every
    field defaults to blank/empty, meaning "use the built-in smart default the
    pass builders already compute" — so a card with no design row behaves exactly
    as before. A stored value overrides that default.

    Apple field slots are JSON lists of ``{"label": str, "source": str}`` where
    ``source`` is a value token (see ``wallets.design.VALUE_TOKENS``) or
    ``"text:<literal>"`` for static text. Google is more constrained (title +
    subtitle + a couple of module rows), mirroring what each platform renders.
    """

    card = models.OneToOneField(Card, on_delete=models.CASCADE, related_name="wallet_design")
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="wallet_designs")

    # ── Shared ──────────────────────────────────────────────────────────────
    # bg/fg live on core.Card (color_bg/color_fg); this is the field-label tint.
    label_color = models.CharField(max_length=7, blank=True, validators=[hex_color])

    # ── Apple (the flexible platform) ───────────────────────────────────────
    apple_logo_text = models.CharField(max_length=40, blank=True)  # blank = merchant name
    apple_header = models.JSONField(default=list, blank=True)  # <=3 slots
    apple_primary = models.JSONField(default=list, blank=True)  # <=1 slot
    apple_secondary = models.JSONField(default=list, blank=True)  # <=4 slots
    apple_auxiliary = models.JSONField(default=list, blank=True)  # <=4 slots
    apple_back = models.JSONField(default=list, blank=True)  # extra back fields
    apple_strip_enabled = models.BooleanField(default=True)  # show the stamp grid strip
    # Custom stamp icons (uploaded via /uploads). When both are set the strip is
    # tiled from them (empty for remaining, filled for earned) instead of the
    # drawn circles. Apple/stamp cards only.
    strip_empty_url = models.URLField(blank=True)
    strip_filled_url = models.URLField(blank=True)

    # ── Google (constrained) ────────────────────────────────────────────────
    google_title = models.CharField(max_length=40, blank=True)  # blank = merchant name
    google_subtitle = models.CharField(max_length=60, blank=True)  # blank = program name
    google_rows = models.JSONField(default=list, blank=True)  # module rows <=3 slots

    objects = TenantManager()

    def __str__(self) -> str:
        return f"design({self.card_id})"
