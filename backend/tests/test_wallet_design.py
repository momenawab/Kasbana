"""Tests for the merchant-editable Apple/Google pass design (notes 2-4)."""

from __future__ import annotations

import pytest
from rest_framework_simplejwt.tokens import RefreshToken

from billing.services import activate_plan
from core.enums import PlanTier
from tests import factories
from wallets.apple.passdata import build_pass_json
from wallets.google.builders import build_loyalty_object
from wallets.models import WalletCardDesign

pytestmark = pytest.mark.django_db


def _url(card) -> str:
    return f"/api/v1/cards/{card.id}/wallet-design"


# ── Endpoint: auth / gating / validation / tenancy ────────────────────────────
def test_get_returns_defaults(auth_client, card):
    resp = auth_client.get(_url(card))
    assert resp.status_code == 200
    body = resp.json()
    assert body["apple_strip_enabled"] is True
    assert body["apple_secondary"] == []
    assert body["apple_logo_text"] == ""


def test_patch_updates_design_on_branded_plan(auth_client, card):
    # The trial fixture resolves to Growth-level, which has custom_branding.
    resp = auth_client.patch(
        _url(card),
        {
            "apple_logo_text": "Cairo Coffee",
            "label_color": "#123456",
            "apple_secondary": [{"label": "LEFT", "source": "remaining"}],
            "apple_back": [{"label": "Note", "source": "text:See you soon"}],
        },
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["apple_logo_text"] == "Cairo Coffee"
    design = WalletCardDesign.objects.get(card=card)
    assert design.apple_secondary == [{"label": "LEFT", "source": "remaining"}]
    assert design.apple_back[0]["source"] == "text:See you soon"


def test_patch_gated_without_custom_branding(auth_client, card, merchant):
    activate_plan(merchant, PlanTier.STARTER)  # custom_branding off
    resp = auth_client.patch(_url(card), {"apple_logo_text": "X"}, format="json")
    assert resp.status_code == 402
    assert resp.json()["error"]["code"] == "PLAN_LIMIT"


def test_patch_rejects_unknown_source(auth_client, card):
    resp = auth_client.patch(
        _url(card),
        {"apple_secondary": [{"label": "L", "source": "wat"}]},
        format="json",
    )
    assert resp.status_code == 400
    assert "apple_secondary" in resp.json()["error"]["fields"]


def test_patch_rejects_too_many_slots(auth_client, card):
    resp = auth_client.patch(
        _url(card),
        {"apple_secondary": [{"label": str(i), "source": "goal"} for i in range(5)]},
        format="json",
    )
    assert resp.status_code == 400


def test_design_is_tenant_scoped(api_client, card):
    other = factories.StaffUserFactory()  # staff of a different merchant
    access = RefreshToken.for_user(other.user).access_token
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    resp = api_client.patch(_url(card), {"apple_logo_text": "X"}, format="json")
    assert resp.status_code == 404


# ── Builders honour the design (blank = smart default) ────────────────────────
def test_passdata_reflects_overrides(customer_card):
    card = customer_card.card
    WalletCardDesign.objects.create(
        card=card,
        merchant=card.merchant,
        apple_logo_text="MyLogo",
        label_color="#AABBCC",
        apple_secondary=[{"label": "STAMPS LEFT", "source": "remaining"}],
        apple_back=[{"label": "Hours", "source": "text:9-5 daily"}],
    )
    payload = build_pass_json(customer_card)
    assert payload["logoText"] == "MyLogo"
    assert payload["labelColor"] == "rgb(170, 187, 204)"
    sec = payload["storeCard"]["secondaryFields"]
    assert sec[0]["label"] == "STAMPS LEFT"
    # Custom back field appended after the computed ones.
    assert any(f["value"] == "9-5 daily" for f in payload["storeCard"]["backFields"])


def test_strip_disabled_leads_with_primary(customer_card):
    card = customer_card.card
    card.stamps_required = 8
    card.save(update_fields=["stamps_required"])
    WalletCardDesign.objects.create(card=card, merchant=card.merchant, apple_strip_enabled=False)
    payload = build_pass_json(customer_card)
    # With no strip, the primary area shows the balance instead of being clear.
    assert payload["storeCard"]["primaryFields"] != []


def test_custom_strip_bg_is_applied(customer_card):
    """The strip band uses the merchant's strip color when set (else darkened bg)."""
    from wallets.apple.signing import _render_stamp_strip

    card = customer_card.card
    card.stamps_required = 6
    card.color_bg = "#2244AA"
    card.save(update_fields=["stamps_required", "color_bg"])
    WalletCardDesign.objects.create(
        card=card, merchant=card.merchant, strip_bg_color="#112233"
    )
    from wallets.apple.signing import build_pass_images

    imgs = build_pass_images(customer_card)
    assert "strip@3x.png" in imgs  # strip rendered
    # A directly-rendered strip with the custom color has that pixel at (0,0).
    from io import BytesIO

    from PIL import Image

    strip = Image.open(BytesIO(imgs["strip@3x.png"])).convert("RGB")
    assert strip.getpixel((0, 0)) == (0x11, 0x22, 0x33)
    # The helper is symmetric for any bg tuple.
    canvas = _render_stamp_strip(1, 3, (10, 20, 30), (255, 255, 255), (60, 20))
    assert canvas.convert("RGB").getpixel((0, 0)) == (10, 20, 30)


def test_google_object_reflects_rows(customer_card):
    card = customer_card.card
    WalletCardDesign.objects.create(
        card=card,
        merchant=card.merchant,
        google_subtitle="Members club",
        google_rows=[{"label": "Reward", "source": "reward"}],
    )
    obj = build_loyalty_object(customer_card)
    mods = obj["textModulesData"]
    assert any(m["body"] == "Members club" for m in mods)
    assert any(m["header"] == "Reward" for m in mods)


def test_no_design_keeps_default_pass(customer_card):
    # A card with no design row builds exactly the default pass (no crash).
    payload = build_pass_json(customer_card)
    assert payload["storeCard"]["headerFields"][0]["key"] == "balance"


def test_field_keys_are_globally_unique(customer_card):
    """Apple rejects a pass with duplicate field keys ("Safari cannot download").

    Overriding several regions must not restart keys at f0 in each — regression
    for the notes 2-4 duplicate-key bug.
    """
    card = customer_card.card
    WalletCardDesign.objects.create(
        card=card,
        merchant=card.merchant,
        apple_header=[{"label": "H", "source": "balance"}],
        apple_primary=[{"label": "P", "source": "stamps"}],
        apple_secondary=[{"label": "S1", "source": "remaining"}, {"label": "S2", "source": "goal"}],
        apple_auxiliary=[{"label": "A", "source": "reward"}],
        apple_back=[{"label": "B", "source": "text:hi"}],
    )
    store = build_pass_json(customer_card)["storeCard"]
    keys = [f["key"] for region in store.values() for f in region]
    assert len(keys) == len(set(keys)), f"duplicate field keys: {keys}"
