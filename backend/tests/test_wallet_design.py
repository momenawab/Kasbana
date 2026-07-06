"""Tests for the merchant-editable Apple/Google pass design (templates-only).

Every card renders through a layout-locked template (a card with no design row,
or a legacy ``custom``/unknown key, falls back to its type's default template).
The merchant edits colors/text/data — never field positions. These cover the
per-card design endpoint (auth/gating/validation/tenancy) and the builder
behaviours that still apply under a locked template (label color, appended back
fields, strip color, globally-unique field keys)."""

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


# ── Builders honour the design under a locked template ────────────────────────
def test_passdata_overrides_apply_under_template(customer_card):
    """Under a locked template the label color, the explicit logoText override,
    and appended back fields still apply — but field *positions* (here the
    secondary label) come from the template, not a freeform override."""
    card = customer_card.card
    WalletCardDesign.objects.create(
        card=card,
        merchant=card.merchant,
        template_key="loyalty_stamps",
        apple_logo_text="MyLogo",
        label_color="#AABBCC",
        apple_secondary=[{"label": "STAMPS LEFT", "source": "remaining"}],  # locked out
        apple_back=[{"label": "Hours", "source": "text:9-5 daily"}],
    )
    payload = build_pass_json(customer_card)
    assert payload["logoText"] == "MyLogo"  # explicit override wins over platform label
    assert payload["labelColor"] == "rgb(170, 187, 204)"
    # Secondary label is the template's locked one — the freeform override is ignored.
    assert payload["storeCard"]["secondaryFields"][0]["label"] == "5 FOR A REWARD"
    # Custom back field is still appended after the computed ones.
    assert any(f["value"] == "9-5 daily" for f in payload["storeCard"]["backFields"])


def test_points_default_template_leads_with_primary(customer_card):
    """A POINTS card with no design row renders its default template
    (points_reward, no strip) which leads with the balance in the primary area."""
    card = customer_card.card
    card.type = "POINTS"
    card.save(update_fields=["type"])
    payload = build_pass_json(customer_card)
    assert payload["storeCard"]["primaryFields"] != []


def test_custom_strip_bg_is_applied(customer_card):
    """The strip band uses the merchant's strip color when set (else darkened bg)."""
    from wallets.apple.signing import _render_stamp_strip

    card = customer_card.card
    card.stamps_required = 6
    card.color_bg = "#2244AA"
    card.save(update_fields=["stamps_required", "color_bg"])
    WalletCardDesign.objects.create(card=card, merchant=card.merchant, strip_bg_color="#112233")
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


def test_google_template_rows_render(customer_card):
    # Templates-only: the Google text modules come from the locked template's
    # google layout (loyalty_stamps → subtitle=program + a "Reward" row).
    WalletCardDesign.objects.create(
        card=customer_card.card, merchant=customer_card.merchant, template_key="loyalty_stamps"
    )
    mods = build_loyalty_object(customer_card)["textModulesData"]
    assert any(m["header"] == "Reward" for m in mods)


def test_google_stamp_hero_renders_and_updates_url(customer_card, settings):
    """Enabling the stamp hero puts a rendered banner on the object; the URL is
    content-addressed so a new stamp count yields a fresh URL (Google re-fetches)."""
    settings.BASE_URL = "https://api.stampn.net"
    card = customer_card.card
    card.stamps_required = 6
    card.save(update_fields=["stamps_required"])
    WalletCardDesign.objects.create(card=card, merchant=card.merchant, google_stamp_hero=True)

    customer_card.stamp_count = 2
    customer_card.save(update_fields=["stamp_count"])
    obj = build_loyalty_object(customer_card)
    assert "heroImage" in obj
    url_2 = obj["heroImage"]["sourceUri"]["uri"]
    assert url_2.startswith("https://api.stampn.net/media/google-hero/")

    # A different count produces a different (cache-busting) URL.
    customer_card.stamp_count = 3
    customer_card.save(update_fields=["stamp_count"])
    url_3 = build_loyalty_object(customer_card)["heroImage"]["sourceUri"]["uri"]
    assert url_3 != url_2


def test_no_design_uses_default_locked_template(customer_card):
    # Templates-only: a card with no design row renders its type's default locked
    # template (STAMP → loyalty_stamps), not a freeform layout — no crash. Proven
    # by the template's locked secondary label (the header is now the brand).
    payload = build_pass_json(customer_card)
    assert payload["storeCard"]["secondaryFields"][0]["label"] == "5 FOR A REWARD"


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
