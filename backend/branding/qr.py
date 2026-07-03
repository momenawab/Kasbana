"""Styled QR rendering (Phase 1 · finalize-phases).

Hand-rolls a colored, shaped SVG straight from the ``qrcode`` module matrix — no
raster dependency (Pillow) and fully deterministic, so tests stay hermetic and
the output inlines cleanly on the web. Logo-in-centre + the composed poster PDF
(which need Pillow + served media) land in Phase 3.
"""

from __future__ import annotations

from typing import Any

import qrcode

_DEFAULT_FG = "#000000"
_DEFAULT_BG = "#FFFFFF"


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
