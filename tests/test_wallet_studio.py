"""Wallet Studio — admin-authored pass overlays and strip artwork.

Three things are load-bearing and get the most attention here:

* the **locked keys**, because an overlay that reaches ``serialNumber`` or
  ``webServiceURL`` silently breaks passes already in customers' wallets;
* the **merchant/admin split**, because the raw overlay must not be writable
  through the merchant dashboard's design endpoint;
* the **Google hero fingerprint**, because a pixel change that doesn't change the
  digest means Google keeps serving the cached banner and the edit looks like it
  did nothing.
"""

from __future__ import annotations

import io
import json

import pytest
from rest_framework.test import APIClient

from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminUser
from tests import factories
from wallets import overlay as overlay_mod
from wallets import stamp_grid
from wallets.apple.passdata import build_pass_json
from wallets.models import WalletCardDesign
from wallets.serializers import AdminWalletCardDesignSerializer, WalletCardDesignSerializer

pytestmark = pytest.mark.django_db


def _client(role=AdminRole.SUPER_ADMIN):
    admin = AdminUser(email=f"{role.lower()}-studio@stampn.net", role=role)
    admin.set_password("supersecret1")
    admin.save()
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return c


@pytest.fixture
def admin_client():
    return _client()


@pytest.fixture
def design(card):
    return WalletCardDesign.objects.create(card=card, merchant=card.merchant)


def _design_url(card) -> str:
    return f"/api/admin/v1/merchants/{card.merchant_id}/cards/{card.id}/wallet-design"


# ── merge semantics (wallets.overlay) ─────────────────────────────────────────
def test_merge_is_recursive_for_objects():
    base = {"storeCard": {"headerFields": [1], "backFields": [2]}, "keep": "yes"}
    out = overlay_mod.merge(base, {"storeCard": {"headerFields": [9]}})
    assert out == {"storeCard": {"headerFields": [9], "backFields": [2]}, "keep": "yes"}


def test_merge_replaces_lists_wholesale():
    """An admin writing a field array means "these are the fields", not "append"."""
    out = overlay_mod.merge({"f": [1, 2, 3]}, {"f": [9]})
    assert out["f"] == [9]


def test_merge_null_deletes_a_generated_key():
    """RFC 7386 — how an admin removes a default they don't want."""
    out = overlay_mod.merge({"logoText": "Acme", "keep": 1}, {"logoText": None})
    assert "logoText" not in out and out["keep"] == 1


def test_merge_does_not_mutate_the_base():
    base = {"a": {"b": 1}}
    overlay_mod.merge(base, {"a": {"b": 2}})
    assert base == {"a": {"b": 1}}


def test_apply_strips_locked_keys_even_when_stored():
    """Defence in depth: a row written from the shell can't beat the render path."""
    payload = {"serialNumber": "real", "backgroundColor": "rgb(0, 0, 0)"}
    out = overlay_mod.apply(
        payload,
        {"serialNumber": "hijacked", "backgroundColor": "rgb(255, 0, 0)"},
        None,
        overlay_mod.LOCKED_APPLE,
    )
    assert out["serialNumber"] == "real"
    assert out["backgroundColor"] == "rgb(255, 0, 0)"


def test_apply_is_a_noop_without_an_overlay():
    payload = {"a": 1}
    assert overlay_mod.apply(payload, None, None, overlay_mod.LOCKED_APPLE) == payload
    assert overlay_mod.apply(payload, {}, None, overlay_mod.LOCKED_APPLE) == payload


def test_interpolate_deep_resolves_tokens_at_any_depth():
    ctx = {"remaining": 3, "goal": 8, "merchant": "Acme"}
    out = overlay_mod.interpolate_deep(
        {"a": [{"value": "{remaining} left"}], "b": {"c": "of {goal}"}}, ctx
    )
    assert out["a"][0]["value"] == "3 left"
    assert out["b"]["c"] == "of 8"


def test_interpolate_deep_leaves_unknown_tokens_alone():
    assert overlay_mod.interpolate_deep({"v": "{nope}"}, {"goal": 1})["v"] == "{nope}"


def test_a_lone_token_keeps_its_type():
    """Apple only applies numberStyle to numeric values, so "{remaining}" must
    resolve to the int 3 — not the string "3"."""
    out = overlay_mod.interpolate_deep({"value": "{remaining}"}, {"remaining": 3})
    assert out["value"] == 3
    assert isinstance(out["value"], int)


def test_a_token_inside_a_sentence_stays_a_string():
    out = overlay_mod.interpolate_deep({"value": "{remaining} to go"}, {"remaining": 3})
    assert out["value"] == "3 to go"


def test_interpolate_deep_does_not_touch_keys():
    """Dict keys are pass field names, not content."""
    out = overlay_mod.interpolate_deep({"{goal}": "x"}, {"goal": 8})
    assert list(out) == ["{goal}"]


# ── serializer validation ─────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "key", ["serialNumber", "authenticationToken", "webServiceURL", "barcodes", "voided"]
)
def test_locked_apple_keys_are_rejected_by_name(design, key):
    ser = AdminWalletCardDesignSerializer(design, data={"apple_overlay": {key: "x"}}, partial=True)
    assert not ser.is_valid()
    # Named, not silently dropped — an admin who sees it vanish would keep trying.
    assert key in str(ser.errors["apple_overlay"])


def test_unlocked_apple_keys_are_accepted(design):
    ser = AdminWalletCardDesignSerializer(
        design,
        data={
            "apple_overlay": {
                "suppressStripShine": True,
                "locations": [{"latitude": 30.04, "longitude": 31.23}],
                "semantics": {"totalPrice": {"amount": "0", "currencyCode": "EGP"}},
            }
        },
        partial=True,
    )
    assert ser.is_valid(), ser.errors


def test_google_overlay_rejects_unknown_sections(design):
    ser = AdminWalletCardDesignSerializer(
        design, data={"google_overlay": {"loyaltyObject": {}}}, partial=True
    )
    assert not ser.is_valid()
    assert "loyaltyObject" in str(ser.errors["google_overlay"])


def test_google_overlay_locks_object_identity(design):
    ser = AdminWalletCardDesignSerializer(
        design, data={"google_overlay": {"object": {"classId": "x"}}}, partial=True
    )
    assert not ser.is_valid()
    assert "classId" in str(ser.errors["google_overlay"])


def test_overlay_must_be_an_object(design):
    ser = AdminWalletCardDesignSerializer(design, data={"apple_overlay": [1]}, partial=True)
    assert not ser.is_valid()


def test_oversized_overlay_is_rejected(design):
    big = {"notes": "x" * (overlay_mod.MAX_OVERLAY_BYTES + 1)}
    ser = AdminWalletCardDesignSerializer(design, data={"apple_overlay": big}, partial=True)
    assert not ser.is_valid()


def test_merchant_serializer_cannot_write_overlays():
    """The raw pass payload is a platform tool, not a merchant-facing field."""
    assert "apple_overlay" not in WalletCardDesignSerializer.Meta.fields
    assert "google_overlay" not in WalletCardDesignSerializer.Meta.fields


def test_merchant_endpoint_ignores_an_overlay(auth_client, card):
    resp = auth_client.patch(
        f"/api/v1/cards/{card.id}/wallet-design",
        {"apple_overlay": {"logoText": "sneaky"}},
        format="json",
    )
    assert resp.status_code == 200
    design = WalletCardDesign.objects.get(card=card)
    assert design.apple_overlay == {}


# ── the overlay reaching a real pass ──────────────────────────────────────────
def test_overlay_adds_keys_to_the_apple_pass(customer_card):
    WalletCardDesign.objects.create(
        card=customer_card.card,
        merchant=customer_card.merchant,
        apple_overlay={"suppressStripShine": True, "maxDistance": 500},
    )
    payload = build_pass_json(customer_card)
    assert payload["suppressStripShine"] is True
    assert payload["maxDistance"] == 500


def test_overlay_tokens_resolve_per_customer(card):
    WalletCardDesign.objects.create(
        card=card,
        merchant=card.merchant,
        apple_overlay={"userInfo": {"note": "{remaining} to go"}},
    )
    a = factories.CustomerCardFactory(card=card, merchant=card.merchant, stamp_count=1)
    b = factories.CustomerCardFactory(card=card, merchant=card.merchant, stamp_count=4)
    assert build_pass_json(a)["userInfo"]["note"] == "4 to go"
    assert build_pass_json(b)["userInfo"]["note"] == "1 to go"


def test_overlay_cannot_hijack_the_serial_at_render_time(customer_card):
    """Bypasses the serializer entirely — writes the row directly."""
    WalletCardDesign.objects.create(
        card=customer_card.card,
        merchant=customer_card.merchant,
        apple_overlay={"serialNumber": "hijacked", "webServiceURL": "https://evil.example"},
    )
    payload = build_pass_json(customer_card)
    assert payload["serialNumber"] == str(customer_card.id)
    assert "evil.example" not in payload["webServiceURL"]


def test_strip_artwork_suppresses_the_shine(customer_card):
    WalletCardDesign.objects.create(
        card=customer_card.card,
        merchant=customer_card.merchant,
        strip_bg_image_url="https://cdn.example/art.png",
    )
    assert build_pass_json(customer_card)["suppressStripShine"] is True


def test_no_shine_suppression_without_artwork(customer_card):
    WalletCardDesign.objects.create(card=customer_card.card, merchant=customer_card.merchant)
    assert "suppressStripShine" not in build_pass_json(customer_card)


# ── strip artwork rendering ───────────────────────────────────────────────────
def _png_bytes(size=(400, 400), color=(200, 30, 30, 255)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize("size", [(1125, 369), (1032, 336)])
def test_cover_crop_fills_both_canvases_without_distortion(size):
    """One upload has to work at the Apple strip AND the Google hero ratio."""
    from PIL import Image

    src = Image.open(io.BytesIO(_png_bytes((400, 400)))).convert("RGBA")
    out = stamp_grid.cover_crop(src, size)
    assert out.size == size


def test_cover_crop_crops_rather_than_letterboxes():
    """A tall source must fill the wide band edge to edge — no transparent bars."""
    from PIL import Image

    src = Image.open(io.BytesIO(_png_bytes((100, 900)))).convert("RGBA")
    out = stamp_grid.cover_crop(src, (1125, 369))
    assert out.getpixel((0, 0))[3] == 255
    assert out.getpixel((1124, 368))[3] == 255


def test_artwork_replaces_the_flat_panel():
    plain = stamp_grid.render_stamp_grid(1, 5, (11, 122, 91), (255, 255, 255), (300, 100))
    arty = stamp_grid.render_stamp_grid(
        1, 5, (11, 122, 91), (255, 255, 255), (300, 100), background=_png_bytes()
    )
    assert plain.tobytes() != arty.tobytes()
    # Top-left corner is band background, never a stamp — so it is the artwork.
    assert arty.getpixel((2, 2))[:3] == (200, 30, 30)


def test_stamps_hidden_renders_artwork_alone():
    with_stamps = stamp_grid.render_stamp_grid(
        3, 5, (11, 122, 91), (255, 255, 255), (300, 100), background=_png_bytes()
    )
    without = stamp_grid.render_stamp_grid(
        3,
        5,
        (11, 122, 91),
        (255, 255, 255),
        (300, 100),
        background=_png_bytes(),
        stamps_visible=False,
    )
    assert with_stamps.tobytes() != without.tobytes()
    # Nothing drawn on top: every pixel is the (uniform) artwork colour.
    assert without.getpixel((150, 50))[:3] == (200, 30, 30)


def test_unusable_artwork_falls_back_to_the_flat_panel():
    """A bad upload must degrade to the old look, not break every pass."""
    out = stamp_grid.render_stamp_grid(
        1, 5, (11, 122, 91), (255, 255, 255), (300, 100), background=b"not a png"
    )
    assert out.getpixel((2, 2))[:3] == (11, 122, 91)


def test_google_hero_fingerprint_covers_the_artwork_fields(customer_card, monkeypatch):
    """Google caches by URL — a pixel change that doesn't move the digest is invisible."""
    from wallets.google import hero

    monkeypatch.setattr(hero, "_local_media_bytes", lambda url: None)
    design = WalletCardDesign.objects.create(
        card=customer_card.card, merchant=customer_card.merchant, google_stamp_hero=True
    )
    first = hero.stamp_hero_url(customer_card)

    design.strip_bg_image_url = "https://cdn.example/art.png"
    design.save()
    customer_card.card.refresh_from_db()
    second = hero.stamp_hero_url(customer_card)

    assert first and second and first != second


# ── endpoints ─────────────────────────────────────────────────────────────────
def test_card_list_is_scoped_to_the_merchant(admin_client, card):
    other = factories.CardFactory()
    resp = admin_client.get(f"/api/admin/v1/merchants/{card.merchant_id}/cards")
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.json()}
    assert str(card.id) in ids and str(other.id) not in ids


def test_card_from_another_merchant_is_404(admin_client, card):
    """The merchant id in the path is a guard, not decoration."""
    other = factories.CardFactory()
    resp = admin_client.get(
        f"/api/admin/v1/merchants/{card.merchant_id}/cards/{other.id}/wallet-design"
    )
    assert resp.status_code == 404


@pytest.mark.parametrize(
    "role", [AdminRole.SUPPORT, AdminRole.SALES, AdminRole.FINANCE, AdminRole.READ_ONLY]
)
def test_studio_is_super_admin_only(card, role):
    """A saved overlay re-renders passes already in customers' wallets."""
    resp = _client(role).get(_design_url(card))
    assert resp.status_code == 403


def test_patch_saves_an_overlay(admin_client, card, monkeypatch):
    from wallets.tasks import sync_google_class

    monkeypatch.setattr(sync_google_class, "delay", lambda card_id: None)
    resp = admin_client.patch(
        _design_url(card),
        {"apple_overlay": {"maxDistance": 250}, "strip_stamps_visible": False},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    design = WalletCardDesign.objects.get(card=card)
    assert design.apple_overlay == {"maxDistance": 250}
    assert design.strip_stamps_visible is False


def test_patch_rejects_a_locked_key(admin_client, card):
    resp = admin_client.patch(
        _design_url(card), {"apple_overlay": {"serialNumber": "x"}}, format="json"
    )
    assert resp.status_code == 400
    assert "serialNumber" in resp.content.decode()


def test_admin_patch_is_not_blocked_by_the_template_allowlist(admin_client, card, monkeypatch):
    """The merchant serializer drops non-editable fields; the admin one must not."""
    from wallets.tasks import sync_google_class

    monkeypatch.setattr(sync_google_class, "delay", lambda card_id: None)
    resp = admin_client.patch(
        _design_url(card),
        {"template_key": "minimal", "google_subtitle": "Members club"},
        format="json",
    )
    assert resp.status_code == 200
    design = WalletCardDesign.objects.get(card=card)
    assert design.google_subtitle == "Members club"


def test_preview_renders_without_saving(admin_client, card):
    url = f"/api/admin/v1/merchants/{card.merchant_id}/cards/{card.id}/pass-preview"
    resp = admin_client.post(url, {"design": {"apple_overlay": {"maxDistance": 99}}}, format="json")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["apple"]["maxDistance"] == 99
    assert body["errors"] == {}
    # Nothing persisted — the candidate design was in-memory only.
    design = WalletCardDesign.objects.filter(card=card).first()
    assert design is None or design.apple_overlay == {}


def test_preview_creates_no_customer_or_shortcode(admin_client, card):
    from core.models import CustomerCard
    from wallets.models import CardShortCode

    url = f"/api/admin/v1/merchants/{card.merchant_id}/cards/{card.id}/pass-preview"
    assert admin_client.post(url, {}, format="json").status_code == 200
    assert not CustomerCard.objects.filter(card=card).exists()
    assert not CardShortCode.objects.exists()


def test_preview_reports_a_bad_overlay_as_an_error(admin_client, card):
    resp = admin_client.post(
        f"/api/admin/v1/merchants/{card.merchant_id}/cards/{card.id}/pass-preview",
        {"design": {"apple_overlay": {"serialNumber": "x"}}},
        format="json",
    )
    assert resp.status_code == 400


def test_republish_counts_the_passes_it_queued(admin_client, card, monkeypatch):
    from wallets import service as wallet_service
    from wallets.tasks import sync_google_class

    monkeypatch.setattr(sync_google_class, "delay", lambda card_id: None)
    pushed: list[str] = []
    monkeypatch.setattr(wallet_service, "push_update", lambda cc: pushed.append(str(cc.id)))
    factories.CustomerCardFactory(card=card, merchant=card.merchant)
    factories.CustomerCardFactory(card=card, merchant=card.merchant)

    resp = admin_client.post(
        f"/api/admin/v1/merchants/{card.merchant_id}/cards/{card.id}/republish", {}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["customer_cards"] == 2
    assert len(pushed) == 2


# ── the whole card as one JSON document ───────────────────────────────────────
def _json_url(card) -> str:
    return f"/api/admin/v1/merchants/{card.merchant_id}/cards/{card.id}/card-json"


@pytest.fixture
def no_sync(monkeypatch):
    from wallets.tasks import sync_google_class

    monkeypatch.setattr(sync_google_class, "delay", lambda card_id: None)


def test_document_carries_every_section(admin_client, card):
    body = admin_client.get(_json_url(card)).json()
    assert set(body) == {
        "card",
        "design",
        "apple_overlay",
        "google_overlay",
        "platform",
        "assets",
    }
    assert body["card"]["stamps_required"] == card.stamps_required
    assert "template_key" in body["design"]


def test_document_shows_the_platform_keys_it_will_not_let_you_write(admin_client, card):
    """The complaint this answers: the pass looked half-missing without them."""
    platform = admin_client.get(_json_url(card)).json()["platform"]
    for key in ("passTypeIdentifier", "teamIdentifier", "webServiceURL", "barcodes"):
        assert key in platform


def test_document_redacts_the_per_pass_secret(admin_client, card):
    platform = admin_client.get(_json_url(card)).json()["platform"]
    assert "secret" in platform["authenticationToken"]
    # The real token must not be echoed to a screen.
    assert len(platform["authenticationToken"]) > 20
    assert platform["serialNumber"].startswith("<")


def test_document_lists_the_image_slots(admin_client, card):
    """Pixels are not JSON — but which upload feeds which file is."""
    assets = admin_client.get(_json_url(card)).json()["assets"]
    files = {a["file"] for a in assets}
    assert {"icon.png", "logo.png", "strip.png"} <= files
    assert all(a["source_field"] for a in assets)


def test_put_writes_card_design_and_overlay_in_one_go(admin_client, card, no_sync):
    resp = admin_client.put(
        _json_url(card),
        {
            "card": {"name": "Renamed", "reward_title": "Free pastry"},
            "design": {"stamp_scale": 1.3, "stamp_color": "#FFAA00"},
            "apple_overlay": {"maxDistance": 120},
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    card.refresh_from_db()
    design = WalletCardDesign.objects.get(card=card)
    assert card.name == "Renamed"
    assert card.reward_title == "Free pastry"
    assert design.stamp_scale == 1.3
    assert design.apple_overlay == {"maxDistance": 120}


def test_put_rejects_a_bad_card_field_under_its_own_section(admin_client, card, no_sync):
    """The editor has to be able to say WHICH half is wrong."""
    resp = admin_client.put(_json_url(card), {"card": {"type": "NONSENSE"}}, format="json")
    assert resp.status_code == 400
    assert "card" in resp.json().get("error", {}).get("fields", resp.json())


def test_put_rejects_a_locked_overlay_key_under_design(admin_client, card, no_sync):
    resp = admin_client.put(
        _json_url(card), {"apple_overlay": {"serialNumber": "x"}}, format="json"
    )
    assert resp.status_code == 400
    assert "serialNumber" in resp.content.decode()


def test_put_ignores_provisioning_output(admin_client, card, no_sync):
    """google_class_id is written by the sync task; editing it orphans the pass."""
    before = card.google_class_id
    admin_client.put(_json_url(card), {"card": {"google_class_id": "hijacked"}}, format="json")
    card.refresh_from_db()
    assert card.google_class_id == before


def test_put_keeps_the_reward_row_in_step_with_the_goal(admin_client, card, no_sync):
    """Changing the goal from JSON must not break the till's redeem button."""
    from core.models import Reward

    admin_client.put(_json_url(card), {"card": {"stamps_required": 12}}, format="json")
    card.refresh_from_db()
    assert card.stamps_required == 12
    assert Reward.objects.filter(card=card, threshold=12).exists()


def test_put_audits_holder_affecting_edits(admin_client, card, no_sync):
    from console.models import AdminAuditLog

    admin_client.put(_json_url(card), {"card": {"stamps_required": 9}}, format="json")
    entry = AdminAuditLog.objects.filter(action="wallet_studio.card_json.update").first()
    assert entry is not None
    assert "stamps_required" in entry.metadata["holder_affecting"]


def test_card_json_is_super_admin_only(card):
    assert _client(AdminRole.SUPPORT).get(_json_url(card)).status_code == 403


def test_card_json_is_tenant_scoped(admin_client, card):
    other = factories.CardFactory()
    url = f"/api/admin/v1/merchants/{card.merchant_id}/cards/{other.id}/card-json"
    assert admin_client.get(url).status_code == 404


# ── sizing ────────────────────────────────────────────────────────────────────
def test_stamp_scale_changes_the_glyph_but_not_the_positions():
    small = stamp_grid.stamp_geometry(6, "grid", (1125, 369), 0.8)
    big = stamp_grid.stamp_geometry(6, "grid", (1125, 369), 1.4)
    assert big["radius"] > small["radius"]
    assert big["icon_w"] > small["icon_w"]
    assert big["icon_h"] > small["icon_h"]
    # Arrangement is the template's job — a size control must not move anything.
    assert big["centers"] == small["centers"]


def test_default_scale_is_byte_identical_to_before():
    """1.0 must render exactly what every existing card renders today."""
    assert stamp_grid.stamp_geometry(6, "grid", (1125, 369)) == stamp_grid.stamp_geometry(
        6, "grid", (1125, 369), 1.0
    )


@pytest.mark.parametrize("bad", [0.1, 3.0, "big"])
def test_out_of_range_stamp_scale_is_rejected(design, bad):
    ser = AdminWalletCardDesignSerializer(design, data={"stamp_scale": bad}, partial=True)
    assert not ser.is_valid()


def test_logo_scale_cannot_exceed_the_apple_slot(design):
    """Apple caps the logo at 160x50 pt; allowing 1.4 would silently do nothing."""
    assert not AdminWalletCardDesignSerializer(
        design, data={"logo_scale": 1.4}, partial=True
    ).is_valid()
    assert AdminWalletCardDesignSerializer(
        design, data={"logo_scale": 1.0}, partial=True
    ).is_valid()


def test_a_small_logo_is_scaled_up_to_fill_the_slot(customer_card, monkeypatch, tmp_path):
    """thumbnail() only ever shrinks, so a modest upload used to render undersized."""
    from PIL import Image

    from wallets.apple import signing

    buf = io.BytesIO()
    Image.new("RGBA", (40, 12), (255, 0, 0, 255)).save(buf, format="PNG")
    monkeypatch.setattr(signing, "_local_media_bytes", lambda url: buf.getvalue())
    customer_card.card.logo_url = "https://cdn.example/logo.png"
    customer_card.card.save()

    images = signing.build_pass_images(customer_card)
    logo = Image.open(io.BytesIO(images["logo.png"]))
    # 40x12 fitted into the 160x50 slot is height-bound: 12 -> 50, i.e. ~166 wide
    # capped by width 160. Either way it must be far larger than the 40px source.
    assert logo.width > 100


def test_google_hero_fingerprint_covers_stamp_scale(customer_card, monkeypatch):
    from wallets.google import hero

    monkeypatch.setattr(hero, "_local_media_bytes", lambda url: None)
    design = WalletCardDesign.objects.create(
        card=customer_card.card, merchant=customer_card.merchant, google_stamp_hero=True
    )
    first = hero.stamp_hero_url(customer_card)
    design.stamp_scale = 1.3
    design.save()
    customer_card.card.refresh_from_db()
    assert first != hero.stamp_hero_url(customer_card)


# ── pass scaffold (the JSON tab's starting point) ─────────────────────────────
def _scaffold_url(card) -> str:
    return f"/api/admin/v1/merchants/{card.merchant_id}/cards/{card.id}/pass-scaffold"


def test_scaffold_keeps_tokens_instead_of_one_customer_s_numbers(admin_client, card):
    """The whole point: a scaffold full of literal numbers would freeze every
    holder at the sample balance the moment it was adopted as an overlay."""
    resp = admin_client.get(_scaffold_url(card))
    assert resp.status_code == 200, resp.content
    body = resp.json()
    blob = json.dumps(body["apple"])
    # The default stamp template puts {balance} in the header and {remaining} in
    # a secondary field; at least one token must survive un-resolved.
    assert "{balance}" in blob or "{remaining}" in blob


def test_scaffold_strips_locked_keys_so_it_can_be_copied_wholesale(admin_client, card):
    resp = admin_client.get(_scaffold_url(card))
    apple = resp.json()["apple"]
    for key in overlay_mod.LOCKED_APPLE:
        assert key not in apple


def test_scaffold_output_is_accepted_as_an_overlay(admin_client, card, monkeypatch):
    """Copy → Save has to work in one hop, or the feature is theatre."""
    from wallets.tasks import sync_google_class

    monkeypatch.setattr(sync_google_class, "delay", lambda card_id: None)
    scaffold = admin_client.get(_scaffold_url(card)).json()

    resp = admin_client.patch(
        _design_url(card), {"apple_overlay": scaffold["apple"]}, format="json"
    )
    assert resp.status_code == 200, resp.content


def test_scaffold_round_trips_back_to_real_values(admin_client, card, monkeypatch):
    """Adopting the scaffold must not change what a customer sees — the tokens it
    preserved resolve again on render."""
    from wallets.tasks import sync_google_class

    monkeypatch.setattr(sync_google_class, "delay", lambda card_id: None)
    holder = factories.CustomerCardFactory(card=card, merchant=card.merchant, stamp_count=2)
    before = build_pass_json(holder)

    scaffold = admin_client.get(_scaffold_url(card)).json()
    admin_client.patch(_design_url(card), {"apple_overlay": scaffold["apple"]}, format="json")

    holder.refresh_from_db()
    after = build_pass_json(holder)
    assert after["storeCard"] == before["storeCard"]


def test_scaffold_reflects_the_saved_design(admin_client, card, monkeypatch):
    from wallets.tasks import sync_google_class

    monkeypatch.setattr(sync_google_class, "delay", lambda card_id: None)
    admin_client.patch(_design_url(card), {"label_color": "#123456"}, format="json")
    apple = admin_client.get(_scaffold_url(card)).json()["apple"]
    assert apple["labelColor"] == "rgb(18, 52, 86)"


def test_scaffold_creates_nothing(admin_client, card):
    from core.models import CustomerCard
    from wallets.models import CardShortCode

    assert admin_client.get(_scaffold_url(card)).status_code == 200
    assert not CustomerCard.objects.filter(card=card).exists()
    assert not CardShortCode.objects.exists()


def test_scaffold_is_super_admin_only(card):
    assert _client(AdminRole.SUPPORT).get(_scaffold_url(card)).status_code == 403


def test_token_context_covers_every_value_token():
    """A token missing here would silently render as an empty string."""
    from wallets.design import VALUE_TOKENS
    from wallets.preview import token_context

    ctx = token_context()
    assert set(ctx) == set(VALUE_TOKENS)
    assert all(ctx[token] == "{" + token + "}" for token in VALUE_TOKENS)


def test_template_catalog_matches_the_merchant_one(admin_client):
    """One source of truth: the studio and the dashboard read the same registry."""
    from wallets import templates as templates_mod

    resp = admin_client.get("/api/admin/v1/wallet-studio/templates")
    assert resp.status_code == 200
    keys = [tpl["key"] for tpl in resp.json()["templates"]]
    assert keys == [tpl["key"] for tpl in templates_mod.template_choices()]


def test_template_catalog_is_super_admin_only():
    resp = _client(AdminRole.SUPPORT).get("/api/admin/v1/wallet-studio/templates")
    assert resp.status_code == 403


def test_upload_is_super_admin_only():
    resp = _client(AdminRole.SALES).post("/api/admin/v1/wallet-studio/uploads", {})
    assert resp.status_code == 403


def test_strip_artwork_is_editable_on_stamp_templates():
    """The merchant editor hides a field the template doesn't list as editable."""
    from wallets import templates as templates_mod

    for key in ("loyalty_stamps", "coffee_stamps"):
        editable = templates_mod.TEMPLATES[key]["editable"]
        assert "strip_bg_image_url" in editable
        assert "strip_stamps_visible" in editable


def test_saving_a_design_does_not_push_to_live_passes(admin_client, card, monkeypatch):
    """Iterating on a design must not fire a wallet push per save."""
    from wallets import service as wallet_service
    from wallets.tasks import sync_google_class

    monkeypatch.setattr(sync_google_class, "delay", lambda card_id: None)
    pushed: list[str] = []
    monkeypatch.setattr(wallet_service, "push_update", lambda cc: pushed.append(str(cc.id)))
    factories.CustomerCardFactory(card=card, merchant=card.merchant)

    admin_client.patch(_design_url(card), {"label_color": "#112233"}, format="json")
    assert pushed == []
