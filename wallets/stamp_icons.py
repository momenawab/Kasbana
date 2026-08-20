"""Built-in stamp icons — a small library of loyalty-stamp glyphs a merchant can
pick (instead of uploading a custom PNG) and tint to the card's stamp color.

Each icon ships as two alpha-mask PNGs under ``stamp_icons/``: ``<key>-filled.png``
(the collected state) and ``<key>-outline.png`` (the remaining state). At pass
build time the chosen mask is tinted with the stamp color — the filled glyph
solid, the outline glyph faded — so the strip reads like a punch card. Only the
alpha channel of each mask matters (the glyph shape); the color comes entirely
from ``stamp_color``. Runtime needs only Pillow (the masks are pre-rasterized from
Phosphor SVGs at build time), so there is no SVG dependency here.
"""

from __future__ import annotations

import io
from pathlib import Path

_RGB = tuple[int, int, int]
_DIR = Path(__file__).resolve().parent / "stamp_icons"

# Registry order = the order shown in the picker. Keep in sync with the frontend
# stamp-icon list (frontend/dashboard/src/components/stampIcons.js) and the PNG
# asset files in ``stamp_icons/``.
ICON_KEYS: tuple[str, ...] = (
    "coffee",
    "star",
    "heart",
    "gift",
    "crown",
    "pizza",
    "icecream",
    "scissors",
    "paw",
    "ticket",
)

# How faded the "remaining" (outline) glyph is relative to the solid filled one,
# so an empty slot reads as not-yet-collected. Mirrors the frontend preview.
_EMPTY_ALPHA = 0.45


def is_valid(key: str | None) -> bool:
    """True if ``key`` names a bundled built-in stamp icon."""
    return bool(key) and key in ICON_KEYS


def _tint(path: Path, color: _RGB, alpha_scale: float):  # type: ignore[no-untyped-def]
    from PIL import Image

    mask = Image.open(path).convert("RGBA")
    alpha = mask.getchannel("A")
    if alpha_scale != 1.0:
        alpha = alpha.point(lambda p: int(p * alpha_scale))
    glyph = Image.new("RGBA", mask.size, (*color, 0))
    glyph.putalpha(alpha)
    return glyph


def _to_png(img) -> bytes:  # type: ignore[no-untyped-def]
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def tinted_pair(key: str, color: _RGB) -> tuple[bytes | None, bytes | None]:
    """Return ``(empty, filled)`` PNG bytes for ``key`` tinted with ``color``.

    ``(None, None)`` for an unknown key or an unreadable asset, so the caller
    falls back to the default drawn circles.
    """
    if not is_valid(key):
        return None, None
    try:
        filled = _tint(_DIR / f"{key}-filled.png", color, 1.0)
        empty = _tint(_DIR / f"{key}-outline.png", color, _EMPTY_ALPHA)
        return _to_png(empty), _to_png(filled)
    except Exception:  # pragma: no cover - missing/broken asset
        return None, None


def resolve_stamp_render(
    design,  # type: ignore[no-untyped-def]
    base_fg: _RGB,
    uploaded_empty: bytes | None,
    uploaded_filled: bytes | None,
) -> tuple[_RGB, bytes | None, bytes | None]:
    """Resolve the stamp foreground color + ``(empty, filled)`` icon bytes.

    Priority: an uploaded custom pair wins (unchanged legacy behavior); else a
    built-in ``stamp_icon`` tinted with ``stamp_color``; else the drawn circles.
    ``stamp_color`` (when set) also recolors the drawn circles, so picking a color
    alone — no icon — still customizes the stamps. Returns
    ``(fg, empty_bytes, filled_bytes)`` ready to hand to ``render_stamp_grid``.
    """
    from wallets.stamp_grid import hex_to_rgb

    fg = hex_to_rgb(design.stamp_color, base_fg) if (design and design.stamp_color) else base_fg
    empty, filled = uploaded_empty, uploaded_filled
    if design and not (empty and filled) and is_valid(getattr(design, "stamp_icon", "")):
        e, f = tinted_pair(design.stamp_icon, fg)
        if e and f:
            empty, filled = e, f
    return fg, empty, filled
