"""Shared stamp-grid rendering — used by the Apple strip and the Google hero.

Pure Pillow helpers with no Django/model dependencies so both wallet backends
can draw the same coffee-card stamp grid (earned filled, remaining outline, or
tiled from custom empty/filled icons) at their own aspect ratios.
"""

from __future__ import annotations

import io

_RGB = tuple[int, int, int]


def hex_to_rgb(value: str | None, default: _RGB) -> _RGB:
    text = (value or "").lstrip("#")
    if len(text) != 6:
        return default
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError:
        return default


def darken(rgb: _RGB, factor: float = 0.82) -> _RGB:
    """Multiply an RGB toward black so a derived panel reads as a distinct band."""
    return (int(rgb[0] * factor), int(rgb[1] * factor), int(rgb[2] * factor))


def load_icon(data: bytes | None):  # type: ignore[no-untyped-def]
    """Decode custom stamp-icon bytes to an RGBA image, or None if unusable."""
    if not data:
        return None
    try:
        from PIL import Image

        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:  # pragma: no cover - bad image bytes
        return None


def render_stamp_grid(
    earned: int,
    required: int,
    bg: _RGB,
    fg: _RGB,
    size: tuple[int, int],
    empty_icon: bytes | None = None,
    filled_icon: bytes | None = None,
):  # type: ignore[no-untyped-def]
    """Draw the stamp grid on a brand-color panel (earned filled, remaining outline).

    When both ``empty_icon`` and ``filled_icon`` are supplied the cells are tiled
    from those custom PNGs (filled for earned, empty for remaining) instead of the
    default drawn circles.
    """
    from PIL import Image, ImageDraw

    w, h = size
    canvas = Image.new("RGBA", (w, h), (*bg, 255))
    draw = ImageDraw.Draw(canvas)

    n = max(1, min(required, 15))  # cap so a big card doesn't render dust
    earned = max(0, min(earned, n))
    rows = 1 if n <= 5 else 2
    cols = (n + rows - 1) // rows
    pad_x, pad_y = int(w * 0.06), int(h * 0.14)
    cell_w = (w - 2 * pad_x) / cols
    cell_h = (h - 2 * pad_y) / rows
    radius = int(min(cell_w, cell_h) * 0.34)
    ring = max(4, radius // 7)

    icon_filled, icon_empty = load_icon(filled_icon), load_icon(empty_icon)
    use_custom = icon_filled is not None and icon_empty is not None
    icon_size = int(min(cell_w, cell_h) * 0.82)

    for i in range(n):
        r, c = divmod(i, cols)
        # centre the last row if it is short
        in_row = cols if r < rows - 1 else n - cols * (rows - 1)
        row_w = in_row * cell_w
        x0 = (w - row_w) / 2 + c * cell_w + cell_w / 2
        cy = pad_y + r * cell_h + cell_h / 2
        if use_custom:
            icon = icon_filled if i < earned else icon_empty
            try:
                glyph = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                canvas.paste(glyph, (int(x0 - icon_size / 2), int(cy - icon_size / 2)), glyph)
                continue
            except Exception:  # pragma: no cover - fall back to drawn circle
                use_custom = False
        box = [x0 - radius, cy - radius, x0 + radius, cy + radius]
        if i < earned:
            draw.ellipse(box, fill=(*fg, 255))  # earned = solid
        else:
            draw.ellipse(box, outline=(*fg, 150), width=ring)  # remaining = ring
    return canvas
