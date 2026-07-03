"""Theme resolution + entitlement gating (Phase 1 · finalize-phases).

``resolve_theme`` is the single seam the public join page (``enrollment``) and
the QR endpoint (``dashboard``) call. It resolves the effective theme
(card override -> merchant default -> system default) and then **gates the rich
branding** behind the ``custom_branding`` entitlement: free plans always get the
stock look + "Powered by Stampn", exactly like the old headline/tagline gate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from billing import entitlements
from branding.defaults import default_fields_config, default_qr_style
from branding.models import RegistrationTheme

if TYPE_CHECKING:
    from core.models import Card, Merchant

# Fields carried through even for un-branded (free) plans — these are functional,
# not cosmetic: which fields to collect, QR colors, and the legal links.
_FUNCTIONAL_KEYS = ("fields_config", "qr_style", "terms_url", "privacy_url")


def _system_default() -> dict[str, Any]:
    return {
        "template_key": "classic",
        "cover_image_url": "",
        "bg_color": "",
        "accent_color": "",
        "button_text_color": "",
        "font": "system",
        "welcome_body": "",
        "fields_config": default_fields_config(),
        "qr_style": default_qr_style(),
        "terms_url": "",
        "privacy_url": "",
        # White-label by default; forced to False for free plans below.
        "hide_powered_by": True,
    }


def _row_to_dict(theme: RegistrationTheme) -> dict[str, Any]:
    return {
        "template_key": theme.template_key,
        "cover_image_url": theme.cover_image_url,
        "bg_color": theme.bg_color,
        "accent_color": theme.accent_color,
        "button_text_color": theme.button_text_color,
        "font": theme.font,
        "welcome_body": theme.welcome_body,
        "fields_config": theme.fields_config or default_fields_config(),
        "qr_style": theme.qr_style or default_qr_style(),
        "terms_url": theme.terms_url,
        "privacy_url": theme.privacy_url,
        "hide_powered_by": theme.hide_powered_by,
    }


def _effective(merchant: Merchant, card: Card | None) -> dict[str, Any]:
    """Card override, else merchant default, else system default (ungated)."""
    row: RegistrationTheme | None = None
    if card is not None:
        row = RegistrationTheme.objects.filter(merchant=merchant, card=card).first()
    if row is None:
        row = RegistrationTheme.objects.filter(merchant=merchant, card__isnull=True).first()

    data = _system_default()
    if row is not None:
        data.update(_row_to_dict(row))
    return data


def _apply_color_inheritance(data: dict[str, Any], merchant: Merchant, card: Card | None) -> None:
    """Fill blank theme colors from the card's (then merchant's) brand colors.

    Decision: the registration page *inherits* the card's brand identity and only
    diverges where the merchant explicitly set a theme color. Resolved here so the
    public page and the dashboard live-preview share one source of truth.
    """
    card_bg = (getattr(card, "color_bg", "") or "") if card is not None else ""
    card_fg = (getattr(card, "color_fg", "") or "") if card is not None else ""
    brand_bg = card_bg or (merchant.color_bg or "")
    brand_fg = card_fg or (merchant.color_fg or "")
    if not data["accent_color"]:
        data["accent_color"] = brand_bg
    if not data["button_text_color"]:
        data["button_text_color"] = brand_fg


def resolve_theme(merchant: Merchant, card: Card | None = None) -> dict[str, Any]:
    """Return the effective theme for the join page, with branding gated.

    On ``custom_branding`` plans the merchant's full theme applies. Otherwise the
    stock look is forced (template/cover/font/welcome/hide-powered-by reset),
    keeping only the functional bits (which fields to collect, QR colors, legal
    links). Brand-color inheritance is applied last, either way.
    """
    data = _effective(merchant, card)
    if not entitlements.check(merchant, "custom_branding"):
        gated = _system_default()
        for key in _FUNCTIONAL_KEYS:
            gated[key] = data[key]
        gated["hide_powered_by"] = False  # free plans always show the footer
        data = gated

    _apply_color_inheritance(data, merchant, card)
    return data
