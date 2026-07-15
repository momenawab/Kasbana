"""Shared stamp-grid rendering — used by the Apple strip and the Google hero.

Pure Pillow helpers with no Django/model dependencies so both wallet backends
can draw the same coffee-card stamp grid (earned filled, remaining outline, or
tiled from custom empty/filled icons) at their own aspect ratios.
"""

from __future__ import annotations

import io

_RGB = tuple[int, int, int]

# Stamp arrangements. Blank/unknown falls back to GRID, so an unset design keeps
# rendering exactly what it rendered before this option existed.
LAYOUT_GRID = "grid"  # row-major: 6 stamps → 0,1,2 on top; 3,4,5 below
LAYOUT_COLUMNS = "columns"  # column-major: 0,2,4 on top; 1,3,5 below
LAYOUT_STAGGER = "stagger"  # as columns, but the lower row slides half a cell → zigzag
LAYOUTS = (LAYOUT_GRID, LAYOUT_COLUMNS, LAYOUT_STAGGER)


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


def _centers(
    n: int,
    rows: int,
    cols: int,
    w: int,
    pad_x: int,
    pad_y: int,
    cell_w: float,
    cell_h: float,
    layout: str,
) -> tuple[list[tuple[float, float]], float]:
    """Centre point per stamp index, plus the horizontal pitch between them.

    The pitch is returned because it — not ``cell_w`` — sizes the glyphs: the
    alternating layouts pack more columns into the same width, so the stamps have
    to shrink to match or they would collide.
    """
    if layout in (LAYOUT_COLUMNS, LAYOUT_STAGGER) and rows > 1:
        # Both alternate down the rows — stamp i sits on row ``i % rows``, column
        # ``i // rows`` — so a 6-stamp card runs 0,2,4 across the top and 1,3,5
        # across the bottom. They differ only in STAGGER sliding each lower row
        # half a column right, which is what turns the grid into a zigzag.
        units = []
        for i in range(n):
            r, c = i % rows, i // rows
            u = c + 0.5 + (0.5 * r if layout == LAYOUT_STAGGER else 0.0)
            units.append((r, u))
        lo = min(u for _, u in units)
        hi = max(u for _, u in units)
        # +1.0 leaves half a pitch of margin either side, so the row that sticks
        # out furthest (the staggered one) still sits inside the padding.
        pitch = (w - 2 * pad_x) / (hi - lo + 1.0)
        centers = [
            (pad_x + (u - lo + 0.5) * pitch, pad_y + r * cell_h + cell_h / 2) for r, u in units
        ]
        return centers, pitch

    # Default row-major grid. Arithmetic left exactly as it was before layouts
    # existed, so an unset design renders pixel-for-pixel what it always has.
    centers = []
    for i in range(n):
        r, c = divmod(i, cols)
        # centre the last row if it is short
        in_row = cols if r < rows - 1 else n - cols * (rows - 1)
        row_w = in_row * cell_w
        centers.append(((w - row_w) / 2 + c * cell_w + cell_w / 2, pad_y + r * cell_h + cell_h / 2))
    return centers, cell_w


def render_stamp_grid(
    earned: int,
    required: int,
    bg: _RGB,
    fg: _RGB,
    size: tuple[int, int],
    empty_icon: bytes | None = None,
    filled_icon: bytes | None = None,
    layout: str = LAYOUT_GRID,
):  # type: ignore[no-untyped-def]
    """Draw the stamp grid on a brand-color panel (earned filled, remaining outline).

    When both ``empty_icon`` and ``filled_icon`` are supplied the cells are tiled
    from those custom PNGs (filled for earned, empty for remaining) instead of the
    default drawn circles.

    ``layout`` arranges the cells — see ``LAYOUTS``. It only bites on cards that
    wrap to two rows (>5 stamps); a single row has nothing to alternate or offset,
    so it always renders as a plain row.
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

    centers, pitch = _centers(n, rows, cols, w, pad_x, pad_y, cell_w, cell_h, layout)
    radius = int(min(pitch, cell_h) * 0.34)
    ring = max(4, radius // 7)

    icon_filled, icon_empty = load_icon(filled_icon), load_icon(empty_icon)
    use_custom = icon_filled is not None and icon_empty is not None
    icon_size = int(min(pitch, cell_h) * 0.82)

    for i, (x0, cy) in enumerate(centers):
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
