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
