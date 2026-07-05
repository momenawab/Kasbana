"""Tests for layout-locked wallet pass templates + the platform logo slot.

Covers: every card renders through a layout-locked template (``custom``/unknown
falls back to the type's default); template selection drives the Apple/Google
layout; the Apple-vs-Google bottom-visual rule (stamps → Apple strip + per-count
Google hero; image → Apple strip + static Google hero); non-editable variables
are dropped when a template is active; the platform brand renders as Apple
``logoText`` (no footer image); template_key validation; and the
``GET /wallet-templates`` catalog endpoint.
"""

from __future__ import annotations

import io

import pytest

from wallets.apple.passdata import build_pass_json
from wallets.apple.signing import build_pass_images
from wallets.google.builders import build_loyalty_object
from wallets.models import WalletCardDesign

pytestmark = pytest.mark.django_db


def _url(card) -> str:
    return f"/api/v1/cards/{card.id}/wallet-design"


def _png_bytes() -> bytes:
    """A tiny valid PNG (for monkeypatched image fetches)."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(buf, format="PNG")
    return buf.getvalue()


# ── Template drives the layout ────────────────────────────────────────────────
def test_stamp_template_drives_apple_fields(customer_card):
    card = customer_card.card
    WalletCardDesign.objects.create(
        card=card, merchant=card.merchant, template_key="loyalty_stamps"
    )
    store = build_pass_json(customer_card)["storeCard"]
    assert store["headerFields"][0]["label"] == "STAMPS"
    # Label interpolation: "{goal} FOR A REWARD" -> "5 FOR A REWARD".
    assert store["secondaryFields"][0]["label"] == "5 FOR A REWARD"


def test_custom_falls_back_to_default_template(customer_card):
    """Templates-only: a legacy ``custom`` key renders the card type's default
    locked template, and any stored freeform slots are ignored."""
    card = customer_card.card
    WalletCardDesign.objects.create(
        card=card,
        merchant=card.merchant,
        template_key="custom",
        apple_header=[{"label": "MYHDR", "source": "balance"}],
    )
    # Freeform header ignored; the default STAMP template (loyalty_stamps) drives it.
    assert build_pass_json(customer_card)["storeCard"]["headerFields"][0]["label"] == "STAMPS"


def test_unknown_template_falls_back_to_default(customer_card):
    """An unknown key renders the default locked template (never freeform, never breaks)."""
    card = customer_card.card
    WalletCardDesign.objects.create(card=card, merchant=card.merchant, template_key="ghost")
    assert build_pass_json(customer_card)["storeCard"]["headerFields"][0]["label"] == "STAMPS"


def test_template_field_keys_are_unique(customer_card):
    card = customer_card.card
    WalletCardDesign.objects.create(
        card=card, merchant=card.merchant, template_key="loyalty_stamps"
    )
    store = build_pass_json(customer_card)["storeCard"]
    keys = [f["key"] for region in store.values() for f in region]
    assert len(keys) == len(set(keys)), f"duplicate field keys: {keys}"


# ── Apple strip: stamps grid / bottom image + platform logoText ───────────────
def test_stamp_template_renders_strip_no_footer(customer_card):
    card = customer_card.card
    card.stamps_required = 6
    card.save(update_fields=["stamps_required"])
    WalletCardDesign.objects.create(
        card=card, merchant=card.merchant, template_key="loyalty_stamps"
    )
    imgs = build_pass_images(customer_card)
    assert "strip@3x.png" in imgs  # stamp grid in the strip (top)
    # Platform branding moved to Apple logoText — there is no footer.png image slot.
    assert not any(k.startswith("footer") for k in imgs)


def test_platform_label_renders_as_logotext(customer_card, settings):
    """The platform ('Powered by') brand rides in Apple logoText, beside the logo."""
    settings.WALLET_PLATFORM_LABEL = "Stampn"
    WalletCardDesign.objects.create(
        card=customer_card.card, merchant=customer_card.merchant, template_key="loyalty_stamps"
    )
    assert build_pass_json(customer_card)["logoText"] == "Stampn"


def test_merchant_logo_text_overrides_platform_label(customer_card, settings):
    settings.WALLET_PLATFORM_LABEL = "Stampn"
    WalletCardDesign.objects.create(
        card=customer_card.card,
        merchant=customer_card.merchant,
        template_key="loyalty_stamps",
        apple_logo_text="ACME",
    )
    assert build_pass_json(customer_card)["logoText"] == "ACME"


def test_image_template_uses_bottom_image_strip(customer_card, monkeypatch):
    card = customer_card.card
    monkeypatch.setattr(
        "wallets.apple.signing._local_media_bytes", lambda url: _png_bytes() if url else None
    )
    WalletCardDesign.objects.create(
        card=card,
        merchant=card.merchant,
        template_key="store_image",
        bottom_image_url="https://api.test/media/a.png",
    )
    assert "strip@3x.png" in build_pass_images(customer_card)


# ── Google hero: per-count (stamps) vs static (image) ─────────────────────────
def test_stamp_template_hero_changes_per_count(customer_card, settings):
    settings.BASE_URL = "https://api.stampn.net"
    card = customer_card.card
    card.stamps_required = 6
    card.save(update_fields=["stamps_required"])
    WalletCardDesign.objects.create(
        card=card, merchant=card.merchant, template_key="loyalty_stamps"
    )

    customer_card.stamp_count = 2
    customer_card.save(update_fields=["stamp_count"])
    url2 = build_loyalty_object(customer_card)["heroImage"]["sourceUri"]["uri"]

    customer_card.stamp_count = 3
    customer_card.save(update_fields=["stamp_count"])
    url3 = build_loyalty_object(customer_card)["heroImage"]["sourceUri"]["uri"]
    assert url2.startswith("https://api.stampn.net/media/google-hero/")
    assert url2 != url3  # cache-busting per count


def test_image_template_hero_is_static(customer_card, settings, monkeypatch):
    settings.BASE_URL = "https://api.stampn.net"
    monkeypatch.setattr(
        "wallets.google.hero._local_media_bytes", lambda url: _png_bytes() if url else None
    )
    WalletCardDesign.objects.create(
        card=customer_card.card,
        merchant=customer_card.merchant,
        template_key="store_image",
        bottom_image_url="https://api.test/media/a.png",
    )
    url1 = build_loyalty_object(customer_card)["heroImage"]["sourceUri"]["uri"]
    customer_card.stamp_count = 4
    customer_card.save(update_fields=["stamp_count"])
    url2 = build_loyalty_object(customer_card)["heroImage"]["sourceUri"]["uri"]
    assert url1 == url2  # content-addressed by image, not count


def test_none_template_has_no_hero(customer_card, settings):
    settings.BASE_URL = "https://api.stampn.net"
    WalletCardDesign.objects.create(
        card=customer_card.card, merchant=customer_card.merchant, template_key="minimal"
    )
    assert "heroImage" not in build_loyalty_object(customer_card)


# ── Serializer: editable gating + validation ─────────────────────────────────
def test_patch_sets_template_and_drops_non_editable(auth_client, card):
    resp = auth_client.patch(
        _url(card),
        {
            "template_key": "loyalty_stamps",
            "label_color": "#123456",  # editable
            "apple_header": [{"label": "H", "source": "balance"}],  # not editable -> dropped
        },
        format="json",
    )
    assert resp.status_code == 200
    d = WalletCardDesign.objects.get(card=card)
    assert d.template_key == "loyalty_stamps"
    assert d.label_color == "#123456"
    assert d.apple_header == []  # freeform fields ignored under a template


def test_patch_stamps_drops_bottom_image(auth_client, card):
    # bottom_image_url is NOT editable for a stamps template.
    resp = auth_client.patch(
        _url(card),
        {"template_key": "loyalty_stamps", "bottom_image_url": "https://example.com/a.png"},
        format="json",
    )
    assert resp.status_code == 200
    assert WalletCardDesign.objects.get(card=card).bottom_image_url == ""


def test_patch_image_accepts_bottom_image(auth_client, card):
    # bottom_image_url IS editable for an image template; freeform rows dropped.
    resp = auth_client.patch(
        _url(card),
        {
            "template_key": "store_image",
            "bottom_image_url": "https://example.com/a.png",
            "google_rows": [{"label": "R", "source": "reward"}],
        },
        format="json",
    )
    assert resp.status_code == 200
    d = WalletCardDesign.objects.get(card=card)
    assert d.bottom_image_url == "https://example.com/a.png"
    assert d.google_rows == []


def test_patch_rejects_unknown_template(auth_client, card):
    resp = auth_client.patch(_url(card), {"template_key": "ghost"}, format="json")
    assert resp.status_code == 400


def test_patch_rejects_unknown_source(auth_client, card):
    # Freeform validation still runs (custom path).
    resp = auth_client.patch(
        _url(card), {"apple_secondary": [{"label": "L", "source": "wat"}]}, format="json"
    )
    assert resp.status_code == 400


# ── Catalog endpoint ──────────────────────────────────────────────────────────
def test_wallet_templates_endpoint(auth_client):
    resp = auth_client.get("/api/v1/wallet-templates")
    assert resp.status_code == 200
    body = resp.json()
    keys = {t["key"] for t in body["templates"]}
    assert {"loyalty_stamps", "store_image", "minimal"} <= keys
    assert "platform_logo_url" in body
    assert all(
        {"key", "name", "card_types", "bottom_visual", "editable"} <= set(t)
        for t in body["templates"]
    )
