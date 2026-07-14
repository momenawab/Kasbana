"""Shared QR asset rendering for the card QR and the merchant main QR.

Both endpoints render the same three things from a join URL — a styled inline
SVG, and a composed poster PDF stored under ``/media`` — with the same rule: a
rendering failure must never withhold what did succeed. The SVG survives a dead
Pillow; the endpoint survives a dead QR library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rest_framework.request import Request

    from core.models import Card, Merchant


def build_qr_assets(
    request: Request,
    merchant: Merchant,
    card: Card,
    join_url: str,
    *,
    poster_key: str | None = None,
) -> dict[str, Any]:
    """Return ``{"join_url", "qr_svg", "poster_pdf_url"}`` for a join URL.

    ``poster_key`` namespaces the stored poster; leave it unset for the card's
    own poster. The main QR must pass its own key — see ``branding.poster``.
    """
    svg = ""
    theme = None
    try:
        from branding.qr import render_qr_svg
        from branding.services import resolve_theme

        theme = resolve_theme(merchant, card)
        svg = render_qr_svg(join_url, theme["qr_style"])
    except Exception:  # pragma: no cover - QR library unavailable
        theme = None

    poster_url = ""
    if theme is not None:
        try:
            from branding.poster import build_and_store_poster

            poster_url = build_and_store_poster(request, card, theme, join_url, key=poster_key)
        except Exception:  # pragma: no cover - Pillow/storage unavailable
            poster_url = ""

    return {"join_url": join_url, "qr_svg": svg, "poster_pdf_url": poster_url}
