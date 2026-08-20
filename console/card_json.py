"""The whole card as one JSON document — read and written by the Wallet Studio.

Everything that shapes a wallet card lives in three places: the ``Card`` row (the
program), the ``WalletCardDesign`` row (how it renders), and the admin overlays
(raw pass payload). An admin editing "the card" should not have to know which of
the three a given knob lives in, so this assembles them into one document and
takes one back.

Two things are deliberately read-only in that document:

* ``platform`` — the identity keys (``serialNumber``, ``authenticationToken``,
  ``webServiceURL``, ``barcodes``, …). They are echoed back so the document shows
  the *complete* pass instead of looking half-missing, but they are never written:
  a wrong value there breaks passes already in customers' wallets.
* ``assets`` — the image files in the .pkpass. Pixels are not JSON; what *is*
  editable is the source URL each one is rendered from, and those live under
  ``card``/``design`` where they can be changed.
"""

from __future__ import annotations

from typing import Any

from core.models import Card
from wallets.models import WalletCardDesign

# Card fields an admin may write from the document. ``status`` and the
# provisioning output (``google_class_id``) are excluded: status has its own
# lifecycle elsewhere in the console, and google_class_id is written by the
# sync task — editing it would orphan the Google pass.
CARD_FIELDS = (
    "type",
    "name",
    "stamps_required",
    "reward_title",
    "reward_description",
    "color_bg",
    "color_fg",
    "logo_url",
    "hero_image_url",
    "single_use",
    "referral_enabled",
)

# Card fields that change the deal for people who already hold the card. Not
# blocked — an admin fixing a typo'd goal is legitimate — but surfaced to the UI
# so it can warn, and recorded in the audit metadata.
HOLDER_AFFECTING = frozenset({"type", "stamps_required", "single_use"})

# Every image in the bundle, what feeds it, and the size Apple renders it at.
# Sizes are points; the bundle also carries @2x/@3x variants of each.
ASSET_SLOTS = (
    ("icon.png", "29x29 pt", "card.logo_url", "Home screen, notifications. Required by Apple."),
    ("logo.png", "160x50 pt", "card.logo_url", "Top-left of the pass, beside logoText."),
    (
        "strip.png",
        "375x123 pt",
        "design.strip_bg_image_url",
        "The full-bleed band. Stamps are drawn onto it.",
    ),
)


def _platform_keys(card: Card) -> dict[str, Any]:
    """The locked keys, as they really render — with the secret redacted.

    ``authenticationToken`` is a per-pass secret; showing it teaches the wrong
    habit and puts a credential-shaped string on screen for no benefit. The rest
    are shown verbatim because knowing the real ``webServiceURL`` or barcode
    format is genuinely useful when debugging a pass.
    """
    from wallets.apple.passdata import build_pass_json
    from wallets.overlay import LOCKED_APPLE
    from wallets.preview import sample_customer_card

    try:
        full = build_pass_json(sample_customer_card(card))
    except Exception:  # pragma: no cover - defensive; the document still renders
        return {}

    out = {key: full[key] for key in LOCKED_APPLE if key in full}
    if "authenticationToken" in out:
        out["authenticationToken"] = "<per-pass secret, generated per customer>"
    if "serialNumber" in out:
        out["serialNumber"] = "<the customer's card id>"
    return out


def _assets(card: Card, design: WalletCardDesign) -> list[dict[str, Any]]:
    sources = {
        "card.logo_url": card.logo_url,
        "design.strip_bg_image_url": design.strip_bg_image_url,
    }
    return [
        {
            "file": name,
            "size": size,
            "source_field": field,
            "url": sources.get(field, ""),
            "note": note,
        }
        for name, size, field, note in ASSET_SLOTS
    ]


def to_document(card: Card, design: WalletCardDesign) -> dict[str, Any]:
    """Assemble the card, its design and its overlays into one document."""
    from wallets.serializers import AdminWalletCardDesignSerializer

    return {
        "card": {field: getattr(card, field) for field in CARD_FIELDS},
        "design": AdminWalletCardDesignSerializer(design).data,
        "apple_overlay": design.apple_overlay or {},
        "google_overlay": design.google_overlay or {},
        "platform": _platform_keys(card),
        "assets": _assets(card, design),
    }


def apply_document(
    card: Card, design: WalletCardDesign, document: dict[str, Any]
) -> dict[str, Any]:
    """Validate and save a document. Returns what changed, for the audit trail.

    Each half is validated by the serializer that already owns those rules — the
    dashboard's ``CardSerializer`` for the card, ``AdminWalletCardDesignSerializer``
    for everything else — so the studio cannot accept a card the merchant's own
    dashboard would reject. Raises ``ValidationError`` with the offending section
    keyed, so the editor can say *which* half is wrong.
    """
    from rest_framework import serializers as drf

    from dashboard.serializers import CardSerializer
    from wallets.serializers import AdminWalletCardDesignSerializer

    changed: dict[str, Any] = {"card": [], "design": [], "holder_affecting": []}

    card_patch = {k: v for k, v in (document.get("card") or {}).items() if k in CARD_FIELDS}
    if card_patch:
        ser = CardSerializer(card, data=card_patch, partial=True)
        try:
            ser.is_valid(raise_exception=True)
        except drf.ValidationError as exc:
            raise drf.ValidationError({"card": exc.detail}) from exc
        changed["card"] = sorted(ser.validated_data.keys())
        changed["holder_affecting"] = sorted(set(ser.validated_data) & HOLDER_AFFECTING)
        ser.save()

    # The overlays are top-level in the document for convenience, but they are
    # design columns — fold them in so one save covers the whole thing.
    design_patch = dict(document.get("design") or {})
    for key in ("apple_overlay", "google_overlay"):
        if key in document:
            design_patch[key] = document[key]
    if design_patch:
        ser = AdminWalletCardDesignSerializer(design, data=design_patch, partial=True)
        try:
            ser.is_valid(raise_exception=True)
        except drf.ValidationError as exc:
            raise drf.ValidationError({"design": exc.detail}) from exc
        changed["design"] = sorted(ser.validated_data.keys())
        ser.save()

    return changed
