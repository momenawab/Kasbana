"""Wallet pass templates — code-defined, layout-locked pass designs.

A *template* fixes where every field sits on the pass (per platform). The
template author chooses the field layout; the merchant can only change the
template's ``editable`` variables (colors, stamp icons, a bottom image, text
content via the card's own fields, logo). Positions are locked by design — no
user-authored templates, no DB rows for templates.

The same template renders on **both** Apple and Google. The bottom visual
(stamp counter or photo) maps to a different region per platform because
Apple's ``storeCard`` pins the barcode to the very bottom (nothing can sit
below it): on Apple the bottom visual lives in the **strip band at the top**;
on Google it lives **below the QR/balance** (the hero banner). See
``wallet-templates-plan.md`` §2.

This module is the single source of truth the backend renderers **and** the
frontend preview read (exposed via ``GET /api/v1/wallet-templates``).
"""

from __future__ import annotations

from typing import Any

from core.enums import CardType

# The freeform editor key — never a registry entry. Keeps today's behaviour.
CUSTOM = "custom"

# Bottom-visual placement (see module docstring for the Apple-vs-Google rule).
_BOTTOM_STAMPS = "stamps"
_BOTTOM_IMAGE = "image"
_BOTTOM_NONE = "none"

TEMPLATES: dict[str, dict[str, Any]] = {
    "loyalty_stamps": {
        "name": "Loyalty — stamps",
        "card_types": [CardType.STAMP],
        "bottom_visual": _BOTTOM_STAMPS,
        "editable": [
            "color_bg",
            "color_fg",
            "label_color",
            "strip_bg_color",
            "strip_empty_url",
            "strip_filled_url",
            "stamp_icon",
            "stamp_color",
            "stamp_layout",
            "strip_bg_image_url",
            "strip_stamps_visible",
            "stamp_scale",
            "logo",
            "logo_scale",
        ],
        "apple": {
            "header": [{"label": "STAMPS", "source": "balance"}],
            "primary": [],
            "secondary": [{"label": "{goal} FOR A REWARD", "source": "remaining"}],
            "auxiliary": [{"label": "REWARD", "source": "reward"}],
        },
        "google": {
            "title": "merchant",
            "subtitle": "program",
            "rows": [{"label": "Reward", "source": "reward"}],
        },
    },
    "coffee_stamps": {
        "name": "Coffee — stamps",
        "card_types": [CardType.STAMP],
        "bottom_visual": _BOTTOM_STAMPS,
        "editable": [
            "color_bg",
            "color_fg",
            "label_color",
            "strip_bg_color",
            "strip_empty_url",
            "strip_filled_url",
            "stamp_icon",
            "stamp_color",
            "stamp_layout",
            "strip_bg_image_url",
            "strip_stamps_visible",
            "stamp_scale",
            "logo",
            "logo_scale",
        ],
        "apple": {
            "header": [{"label": "VISITS", "source": "balance"}],
            "primary": [],
            "secondary": [{"label": "NEXT REWARD IN", "source": "remaining"}],
            "auxiliary": [{"label": "YOU WIN", "source": "reward"}],
        },
        "google": {
            "title": "merchant",
            "subtitle": "program",
            "rows": [{"label": "Reward", "source": "reward"}],
        },
    },
    "points_reward": {
        "name": "Points — reward",
        "card_types": [CardType.POINTS],
        "bottom_visual": _BOTTOM_NONE,
        "editable": ["color_bg", "color_fg", "label_color", "logo", "logo_scale"],
        "apple": {
            "header": [{"label": "POINTS", "source": "balance"}],
            "primary": [{"label": "Balance", "source": "points"}],
            "secondary": [{"label": "Goal", "source": "goal"}],
            "auxiliary": [{"label": "REWARD", "source": "reward"}],
        },
        "google": {
            "title": "merchant",
            "subtitle": "program",
            "rows": [{"label": "Reward", "source": "reward"}],
        },
    },
    "store_image": {
        "name": "Store card — image",
        "card_types": [CardType.STAMP, CardType.POINTS],
        "bottom_visual": _BOTTOM_IMAGE,
        "editable": [
            "color_bg",
            "color_fg",
            "label_color",
            "bottom_image_url",
            "logo",
            "logo_scale",
        ],
        # The photo owns the strip band, so the primary (over-strip) area stays
        # clear: the balance reads below it in secondary and the reward below
        # that in auxiliary, so neither sits on top of the artwork.
        "apple": {
            "header": [{"label": "POINTS", "source": "balance"}],
            "primary": [],
            "secondary": [{"label": "POINTS", "source": "points"}],
            "auxiliary": [{"label": "REWARD", "source": "reward"}],
        },
        "google": {
            "title": "merchant",
            "subtitle": "program",
            "rows": [],
        },
    },
    "minimal": {
        "name": "Minimal",
        "card_types": [CardType.STAMP, CardType.POINTS],
        "bottom_visual": _BOTTOM_NONE,
        "editable": ["color_bg", "color_fg", "label_color", "logo", "logo_scale"],
        "apple": {
            "header": [{"label": "BALANCE", "source": "balance"}],
            "primary": [],
            "secondary": [{"label": "Reward", "source": "reward"}],
            "auxiliary": [],
        },
        "google": {
            "title": "merchant",
            "subtitle": "program",
            "rows": [],
        },
    },
}

# Keys a label string may interpolate, e.g. "{goal} FOR A REWARD". Resolved
# against ``wallets.design.field_context`` (so {goal}/{remaining}/{balance}/...).
_LABEL_FIELDS = frozenset(
    {"balance", "stamps", "points", "goal", "remaining", "reward", "merchant", "program"}
)


def get_template(key: str | None) -> dict[str, Any] | None:
    """Return the template dict for ``key``, or ``None`` if unknown/``custom``."""
    if not key or key == CUSTOM:
        return None
    return TEMPLATES.get(key)


# Templates-only: every card renders through a layout-locked template so field
# positions are always fixed (the merchant edits colors/text/data, never
# positions). When a card has no template (legacy ``custom``/unknown/missing key)
# we fall back to a sensible default for its type instead of the old freeform
# layout. Keep in sync with the frontend picker's default.
_DEFAULT_BY_TYPE: dict[Any, str] = {
    CardType.STAMP: "loyalty_stamps",
    CardType.POINTS: "points_reward",
}


def default_key_for(card_type: str | None) -> str:
    """The default locked-template key for a card type (STAMP/POINTS)."""
    return _DEFAULT_BY_TYPE.get(card_type, "minimal")


def resolve_template(card_type: str | None, key: str | None) -> dict[str, Any]:
    """Return the active template — never ``None`` (templates-only).

    A known registry ``key`` wins; ``custom``/unknown/missing falls back to the
    card type's default template so positions are always locked.
    """
    return get_template(key) or TEMPLATES[default_key_for(card_type)]


def is_template_key(key: str | None) -> bool:
    """True if ``key`` is ``custom`` or a known registry key (a valid choice)."""
    return key == CUSTOM or key in TEMPLATES


def interpolate(label: str, ctx: dict[str, Any]) -> str:
    """Replace ``{token}`` placeholders in a field label with context values.

    Falls back to the raw label if a token is missing or ``str.format`` fails,
    so a bad template label can never break the pass.
    """
    if not label or "{" not in label:
        return label
    try:
        return label.format(**{k: ctx.get(k, "") for k in _LABEL_FIELDS})
    except (KeyError, IndexError, ValueError):
        return label


def template_choices() -> list[dict[str, Any]]:
    """Compact, frontend-safe list of templates (no platform internals).

    Returned by ``GET /api/v1/wallet-templates``. Includes the per-platform
    fixed layouts (``apple``/``google``) so the dashboard preview can render each
    template faithfully from the same source of truth as the backend renderers.
    ``card_types`` use the enum *values* (strings) so JSON/JS can compare
    directly.
    """
    out: list[dict[str, Any]] = []
    for key, tpl in TEMPLATES.items():
        out.append(
            {
                "key": key,
                "name": tpl["name"],
                "card_types": [ct.value for ct in tpl["card_types"]],
                "bottom_visual": tpl["bottom_visual"],
                "editable": list(tpl["editable"]),
                "apple": dict(tpl["apple"]),
                "google": dict(tpl["google"]),
            }
        )
    return out


def choices_for(card_type: str | None) -> list[dict[str, Any]]:
    """Templates that apply to a given ``card_type`` (``STAMP``/``POINTS``)."""
    return [c for c in template_choices() if card_type in c["card_types"]]
