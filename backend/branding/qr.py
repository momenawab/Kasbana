"""Styled QR rendering (Phase 1 · finalize-phases · Phase 3).

The SVG path hand-rolls a colored, shaped code straight from the ``qrcode``
matrix — no raster dependency and fully deterministic, so it inlines cleanly on
the web and tests stay hermetic. Phase 3 adds a raster path (Pillow): a styled
**PNG** with module drawers + a logo in the centre, and a composed **poster PDF**
(cover / logo-in-QR / reward text) for merchants to print.
"""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any

import qrcode

if TYPE_CHECKING:
    from PIL.Image import Image

_DEFAULT_FG = "#000000"
_DEFAULT_BG = "#FFFFFF"

_RGB = tuple[int, int, int]


def _hex_to_rgb(value: str | None, default: _RGB) -> _RGB:
    """Parse ``#RGB``/``#RRGGBB`` to an ``(r, g, b)`` tuple; ``default`` on junk."""
    text = (value or "").lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return default
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError:
        return default


def render_qr_svg(data: str, qr_style: dict[str, Any] | None = None, *, scale: int = 10) -> str:
    """Return an SVG string for ``data`` styled per ``qr_style``.

    ``qr_style`` keys: ``module_style`` (square|rounded|dots), ``fg_color``,
    ``bg_color``. Unknown/blank values fall back to a plain black-on-white code.
    """
    style = qr_style or {}
    fg = style.get("fg_color") or _DEFAULT_FG
    bg = style.get("bg_color") or _DEFAULT_BG
    module_style = style.get("module_style") or "square"

    qr = qrcode.QRCode(border=2, box_size=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()

    n = len(matrix)
    dim = n * scale
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{dim}" height="{dim}" '
        f'viewBox="0 0 {dim} {dim}" role="img" aria-label="Enrollment QR code">',
        f'<rect width="{dim}" height="{dim}" fill="{bg}"/>',
    ]
    for r, row in enumerate(matrix):
        for c, on in enumerate(row):
            if not on:
                continue
            x = c * scale
            y = r * scale
            if module_style == "dots":
                cx = x + scale / 2
                cy = y + scale / 2
                parts.append(f'<circle cx="{cx}" cy="{cy}" r="{scale / 2}" fill="{fg}"/>')
            elif module_style == "rounded":
                rad = scale * 0.3
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{scale}" height="{scale}" '
                    f'rx="{rad}" ry="{rad}" fill="{fg}"/>'
                )
            else:  # square (default)
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{scale}" height="{scale}" fill="{fg}"/>'
                )
    parts.append("</svg>")
    return "".join(parts)


def render_qr_png(
    data: str,
    qr_style: dict[str, Any] | None = None,
    *,
    logo: Image | None = None,
    box_size: int = 12,
) -> Image:
    """Return a styled QR as a PIL ``Image`` (module drawer + optional centre logo).

    Same ``qr_style`` contract as :func:`render_qr_svg` (``module_style``,
    ``fg_color``, ``bg_color``). When ``logo`` is given it is embedded in the
    centre and the code is rendered at error-correction H so it still scans with
    the logo occluding the middle. Raster-only — imports Pillow lazily so the SVG
    path keeps working where Pillow is absent.
    """
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.colormasks import SolidFillColorMask
    from qrcode.image.styles.moduledrawers.pil import (
        CircleModuleDrawer,
        RoundedModuleDrawer,
        SquareModuleDrawer,
    )

    style = qr_style or {}
    fg = _hex_to_rgb(style.get("fg_color"), (0, 0, 0))
    bg = _hex_to_rgb(style.get("bg_color"), (255, 255, 255))
    drawers = {"dots": CircleModuleDrawer, "rounded": RoundedModuleDrawer}
    drawer_cls = drawers.get(style.get("module_style") or "square", SquareModuleDrawer)

    ec = qrcode.constants.ERROR_CORRECT_H if logo is not None else qrcode.constants.ERROR_CORRECT_M
    qr = qrcode.QRCode(border=2, box_size=box_size, error_correction=ec)
    qr.add_data(data)
    qr.make(fit=True)

    kwargs: dict[str, Any] = {
        "image_factory": StyledPilImage,
        "module_drawer": drawer_cls(),
        "color_mask": SolidFillColorMask(back_color=bg, front_color=fg),
    }
    if logo is not None:
        kwargs["embeded_image"] = logo.convert("RGBA")

    img = qr.make_image(**kwargs)
    return img.get_image().convert("RGB")


def _font(size: int) -> Any:
    """A scalable default font (Pillow >= 10.1); falls back to the bitmap default."""
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - very old Pillow
        return ImageFont.load_default()


def _draw_centered(draw: Any, text: str, y: int, width: int, font: Any, fill: _RGB) -> int:
    """Draw ``text`` horizontally centered in ``width``; return the bottom y."""
    if not text:
        return y
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(((width - (right - left)) / 2, y), text, font=font, fill=fill)
    return y + (bottom - top)


def render_poster_pdf(
    join_url: str,
    theme: dict[str, Any],
    *,
    reward_title: str = "",
    reward_description: str = "",
    logo: Image | None = None,
    cover: Image | None = None,
    headline: str = "Scan to join",
) -> bytes:
    """Compose a printable A4 poster (cover / logo-in-QR / reward text) as PDF bytes.

    Layout, top to bottom: an optional cover band, the styled QR (with the logo in
    its centre) on the theme background, then the headline + reward copy. Raster —
    imports Pillow lazily.
    """
    from PIL import Image as PILImage
    from PIL import ImageDraw, ImageOps

    width, height = 1240, 1754  # ~A4 at 150 dpi
    bg = _hex_to_rgb(theme.get("bg_color"), (255, 255, 255))
    accent = _hex_to_rgb(theme.get("accent_color"), (17, 24, 39))
    # Readable ink: near-black on a light bg, near-white on a dark one.
    ink = (17, 24, 39) if sum(bg) > 382 else (245, 245, 245)

    canvas = PILImage.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(canvas)
    y = 80

    if cover is not None:
        band_h = 380
        fitted = ImageOps.fit(cover.convert("RGB"), (width, band_h))
        canvas.paste(fitted, (0, 0))
        y = band_h + 60

    qr_img = render_qr_png(join_url, theme.get("qr_style"), logo=logo)
    qr_size = 720
    qr_img = qr_img.resize((qr_size, qr_size))
    canvas.paste(qr_img, ((width - qr_size) // 2, y))
    y += qr_size + 60

    y = _draw_centered(draw, headline, y, width, _font(64), accent)
    y += 24
    y = _draw_centered(draw, reward_title, y, width, _font(48), ink)
    if reward_description:
        y += 16
        y = _draw_centered(draw, reward_description, y, width, _font(34), ink)

    buf = BytesIO()
    canvas.save(buf, format="PDF", resolution=150.0)
    return buf.getvalue()
