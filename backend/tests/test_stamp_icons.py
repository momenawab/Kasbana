"""Tests for built-in stamp icons — the pickable, color-tinted loyalty glyphs.

Covers the pure icon module (registry + tint + priority resolver), the design
endpoint (persist/validate/gating of ``stamp_icon`` + ``stamp_color``), and that
the Apple strip actually renders the tinted icon into the pass image.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from billing.services import activate_plan
from core.enums import PlanTier
from wallets import stamp_icons
from wallets.models import WalletCardDesign

pytestmark = pytest.mark.django_db


def _url(card) -> str:
    return f"/api/v1/cards/{card.id}/wallet-design"


class _Design:
    """Minimal stand-in for a WalletCardDesign row."""

    def __init__(self, **kw):
        self.stamp_icon = kw.get("stamp_icon", "")
        self.stamp_color = kw.get("stamp_color", "")
        self.strip_empty_url = kw.get("strip_empty_url", "")
        self.strip_filled_url = kw.get("strip_filled_url", "")


# ── Pure module ───────────────────────────────────────────────────────────────
def test_every_icon_key_has_both_mask_assets():
    assert len(stamp_icons.ICON_KEYS) == 10
    for key in stamp_icons.ICON_KEYS:
        for state in ("outline", "filled"):
            path = stamp_icons._DIR / f"{key}-{state}.png"
            assert path.exists(), f"missing asset {path}"


def test_is_valid():
    assert stamp_icons.is_valid("coffee")
    assert not stamp_icons.is_valid("bogus")
    assert not stamp_icons.is_valid("")
    assert not stamp_icons.is_valid(None)


def test_tinted_pair_uses_the_requested_color():
    color = (209, 52, 91)
    empty, filled = stamp_icons.tinted_pair("coffee", color)
    assert empty and filled
    img = Image.open(io.BytesIO(filled)).convert("RGBA")
    # Every visible (non-transparent) pixel carries the tint color, not the
    # source mask's own color — only the glyph's alpha shape is kept.
    opaque = [(n, px) for n, px in img.getcolors(1 << 24) if px[3] > 0]
    assert opaque, "filled glyph should have visible pixels"
    assert all(px[:3] == color for _, px in opaque)


def test_tinted_pair_unknown_key_is_none():
    assert stamp_icons.tinted_pair("bogus", (0, 0, 0)) == (None, None)


# ── Priority resolver ─────────────────────────────────────────────────────────
def test_resolve_uses_stamp_color_as_fg():
    fg, empty, filled = stamp_icons.resolve_stamp_render(
        _Design(stamp_color="#33CC77"), (255, 255, 255), None, None
    )
    assert fg == (51, 204, 119)
    assert empty is None and filled is None  # color only → drawn circles


def test_resolve_tints_builtin_icon_when_no_upload():
    fg, empty, filled = stamp_icons.resolve_stamp_render(
        _Design(stamp_icon="star", stamp_color="#123456"), (255, 255, 255), None, None
    )
    assert fg == (18, 52, 86)
    assert empty and filled


def test_resolve_uploaded_pair_wins_over_builtin():
    up_empty, up_filled = b"E", b"F"
    fg, empty, filled = stamp_icons.resolve_stamp_render(
        _Design(stamp_icon="coffee", strip_empty_url="x", strip_filled_url="y"),
        (10, 20, 30),
        up_empty,
        up_filled,
    )
    assert (empty, filled) == (up_empty, up_filled)


def test_resolve_falls_back_when_nothing_set():
    fg, empty, filled = stamp_icons.resolve_stamp_render(_Design(), (7, 8, 9), None, None)
    assert fg == (7, 8, 9) and empty is None and filled is None


# ── Design endpoint ───────────────────────────────────────────────────────────
def test_patch_persists_stamp_icon_and_color(auth_client, card):
    resp = auth_client.patch(
        _url(card),
        {"stamp_icon": "coffee", "stamp_color": "#D1345B"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    design = WalletCardDesign.objects.get(card=card)
    assert design.stamp_icon == "coffee"
    assert design.stamp_color == "#D1345B"


def test_patch_rejects_unknown_stamp_icon(auth_client, card):
    resp = auth_client.patch(_url(card), {"stamp_icon": "bogus"}, format="json")
    assert resp.status_code == 400
    assert "stamp_icon" in resp.json().get("error", {}).get("fields", resp.json())


def test_stamp_icon_gated_without_custom_branding(auth_client, card, merchant):
    activate_plan(merchant, PlanTier.STARTER)
    resp = auth_client.patch(_url(card), {"stamp_icon": "coffee"}, format="json")
    assert resp.status_code == 402


# ── Apple strip render ────────────────────────────────────────────────────────
def test_apple_strip_reflects_the_chosen_icon(auth_client, card, customer_card):
    from wallets.apple.signing import build_pass_images

    # Earn some stamps so filled (solid-tint) glyphs render, not just outlines.
    customer_card.stamp_count = 3
    customer_card.save(update_fields=["stamp_count"])

    plain = build_pass_images(customer_card)["strip@3x.png"]

    resp = auth_client.patch(
        _url(card), {"stamp_icon": "coffee", "stamp_color": "#D1345B"}, format="json"
    )
    assert resp.status_code == 200, resp.content
    card.refresh_from_db()
    withicon = build_pass_images(customer_card)["strip@3x.png"]

    # The stamp icon + color changes the rendered strip pixels.
    assert plain != withicon
    img = Image.open(io.BytesIO(withicon)).convert("RGB")
    colors = {c for _, c in img.getcolors(1 << 24)}
    assert (209, 52, 91) in colors  # the tint color appears
