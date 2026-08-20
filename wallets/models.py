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
from wallets import stamp_grid

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
    # Background of the stamp strip band. Blank = auto (a slightly darkened brand
    # bg) so the strip reads as its own row instead of blending into the pass.
    strip_bg_color = models.CharField(max_length=7, blank=True, validators=[hex_color])
    # Custom stamp icons (uploaded via /uploads). When both are set the strip is
    # tiled from them (empty for remaining, filled for earned) instead of the
    # drawn circles. Apple/stamp cards only.
    strip_empty_url = models.URLField(blank=True)
    strip_filled_url = models.URLField(blank=True)
    # Built-in stamp icon picked at design time (a key in
    # ``wallets.stamp_icons.ICON_KEYS``, e.g. "coffee"). Blank = default drawn
    # circles. Ignored when a custom ``strip_*_url`` pair is uploaded (that wins).
    stamp_icon = models.CharField(max_length=20, blank=True)
    # Fill color for the stamps (both the built-in icon and the drawn circles).
    # Blank = the card foreground color. Apple/stamp cards only.
    stamp_color = models.CharField(max_length=7, blank=True, validators=[hex_color])
    # How the stamps are arranged. Blank = "grid" — today's row-major layout, so
    # an unset design renders exactly what it always did. "columns" numbers down
    # each column instead of across each row (6 stamps → 0,2,4 on top, 1,3,5
    # below); "stagger" does the same but offsets the lower row half a cell for a
    # zigzag. Only bites on cards that wrap to two rows (>5 stamps). Shared by the
    # Apple strip AND the Google hero — one renderer draws both.
    stamp_layout = models.CharField(
        max_length=12, blank=True, choices=[(k, k) for k in stamp_grid.LAYOUTS]
    )

    # ── Google (constrained) ────────────────────────────────────────────────
    google_title = models.CharField(max_length=40, blank=True)  # blank = merchant name
    google_subtitle = models.CharField(max_length=60, blank=True)  # blank = program name
    google_rows = models.JSONField(default=list, blank=True)  # module rows <=3 slots
    # Render the stamp grid into the Google hero banner and refresh it on every
    # stamp (Google has no Apple-style strip). Uses the same strip colors/icons.
    google_stamp_hero = models.BooleanField(default=False)

    # ── Templates (layout-locked, merchant-customizable) ────────────────────
    # "custom" keeps the freeform editor above unchanged. Any other value is a
    # key in ``wallets.templates.TEMPLATES`` and locks the field positions; the
    # merchant may then edit only that template's ``editable`` variables.
    template_key = models.CharField(max_length=40, default="custom")
    # Full-width bottom image for image-style templates (uploaded via /uploads).
    bottom_image_url = models.URLField(blank=True)

    # ── Strip artwork (Apple strip + Google hero share one renderer) ─────────
    # Photo behind the stamp grid. Blank = the flat brand-color panel that the
    # strip has always drawn. Cover-cropped to each canvas, so the same upload
    # works at the Apple strip and Google hero aspect ratios. When set, the Apple
    # pass also gets ``suppressStripShine`` — Apple's default gloss gradient
    # washes out real artwork.
    strip_bg_image_url = models.URLField(blank=True)
    # Draw the stamps on top of that artwork. False = the artwork alone, for a
    # pure-image band on a card whose progress is shown in the fields instead.
    strip_stamps_visible = models.BooleanField(default=True)

    # ── Sizing ──────────────────────────────────────────────────────────────
    # Neither wallet exposes image dimensions in its pass payload — Apple and
    # Google size the artwork themselves — so these are the only way to change
    # how big things look, and they work by changing the pixels we render.
    #
    # 1.0 keeps exactly what every card rendered before these existed. Bounds are
    # enforced in the serializer: past ~1.5 the stamps collide with each other,
    # and Apple hard-caps the logo slot at 160x50 pt regardless of what is asked.
    stamp_scale = models.FloatField(default=1.0)
    logo_scale = models.FloatField(default=1.0)

    # ── Admin-authored pass JSON overlays (platform admin only) ─────────────
    # Partial JSON merged over the generated payload as the last build step —
    # the escape hatch to pass features the template registry doesn't expose.
    # RFC 7386 semantics with identity keys locked; see ``wallets.overlay``.
    # Not merchant-editable: written only from the admin console Wallet Studio.
    apple_overlay = models.JSONField(default=dict, blank=True)
    # ``{"class": {...}, "object": {...}}`` — Google splits one pass in two.
    google_overlay = models.JSONField(default=dict, blank=True)

    objects = TenantManager()

    def __str__(self) -> str:
        return f"design({self.card_id})"
