"""Tests for the registration theme + styled QR (finalize Phase 1)."""

from __future__ import annotations

import pytest
from rest_framework_simplejwt.tokens import RefreshToken

from billing.services import activate_plan
from branding.models import RegistrationTheme
from branding.qr import render_qr_svg
from branding.services import resolve_theme
from core.enums import PlanTier
from enrollment.tokens import issue_enrollment_token
from tests import factories

pytestmark = pytest.mark.django_db


# ── QR rendering (pure, hermetic) ─────────────────────────────────────────────
def test_render_qr_svg_is_styled_by_qr_style():
    default = render_qr_svg("https://app.stampn.net/enroll/abc")
    assert default.startswith("<svg")
    assert "#000000" in default and "<rect" in default and "<circle" not in default

    styled = render_qr_svg(
        "https://app.stampn.net/enroll/abc",
        {"module_style": "dots", "fg_color": "#1A2B3C", "bg_color": "#FFEECC"},
    )
    assert "<circle" in styled  # dots -> circles
    assert "#1A2B3C" in styled and "#FFEECC" in styled


# ── Theme resolution + entitlement gating ─────────────────────────────────────
def test_resolve_falls_back_to_system_default(merchant, card):
    theme = resolve_theme(merchant, card)
    assert theme["template_key"] == "classic"
    assert theme["qr_style"]["module_style"] == "square"
    assert theme["fields_config"]["name"]["show"] is True


def test_card_override_beats_merchant_default(merchant, card):
    RegistrationTheme.objects.create(merchant=merchant, card=None, accent_color="#111111")
    RegistrationTheme.objects.create(merchant=merchant, card=card, accent_color="#222222")
    assert resolve_theme(merchant, card)["accent_color"] == "#222222"
    assert resolve_theme(merchant, None)["accent_color"] == "#111111"


def test_free_plan_is_gated_to_stock_look(merchant, card):
    # Rich theme stored, but a non-branding plan forces the stock look.
    RegistrationTheme.objects.create(
        merchant=merchant,
        card=None,
        template_key="bold",
        cover_image_url="https://cdn.example/hero.png",
        welcome_body="Fancy copy",
        hide_powered_by=True,
    )
    activate_plan(merchant, PlanTier.STARTER)  # custom_branding off

    theme = resolve_theme(merchant, None)
    assert theme["template_key"] == "classic"  # forced back to stock
    assert theme["cover_image_url"] == ""
    assert theme["welcome_body"] == ""
    assert theme["hide_powered_by"] is False  # free plans always show the footer


def test_branded_plan_keeps_rich_theme(merchant, card):
    RegistrationTheme.objects.create(
        merchant=merchant, card=None, template_key="hero", welcome_body="Hi!"
    )
    activate_plan(merchant, PlanTier.GROWTH)  # custom_branding on
    theme = resolve_theme(merchant, None)
    assert theme["template_key"] == "hero"
    assert theme["welcome_body"] == "Hi!"


# ── Public enroll endpoint carries the theme ──────────────────────────────────
def test_enroll_landing_includes_theme(api_client, card):
    token = issue_enrollment_token(card)
    body = api_client.get(f"/api/v1/enroll/{token.token}").json()
    assert "theme" in body
    assert body["theme"]["template_key"] == "classic"
    assert body["theme"]["qr_style"]["module_style"] == "square"


# ── Editor endpoints (auth, tenancy, validation) ──────────────────────────────
def test_get_and_patch_merchant_theme(auth_client):
    resp = auth_client.get("/api/v1/settings/enroll-theme")
    assert resp.status_code == 200
    assert resp.json()["template_key"] == "classic"

    resp = auth_client.patch(
        "/api/v1/settings/enroll-theme",
        {"template_key": "hero", "accent_color": "#123456"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["accent_color"] == "#123456"


def test_patch_rejects_bad_color(auth_client):
    resp = auth_client.patch(
        "/api/v1/settings/enroll-theme", {"accent_color": "red"}, format="json"
    )
    assert resp.status_code == 400


def test_patch_rejects_unknown_field_config(auth_client):
    resp = auth_client.patch(
        "/api/v1/settings/enroll-theme",
        {"fields_config": {"ssn": {"show": True}}},
        format="json",
    )
    assert resp.status_code == 400


def test_card_theme_override_and_clear(auth_client, card):
    resp = auth_client.patch(
        f"/api/v1/cards/{card.id}/enroll-theme",
        {"accent_color": "#ABCDEF"},
        format="json",
    )
    assert resp.status_code == 200
    assert RegistrationTheme.objects.filter(merchant=card.merchant, card=card).exists()

    resp = auth_client.delete(f"/api/v1/cards/{card.id}/enroll-theme")
    assert resp.status_code == 204
    assert not RegistrationTheme.objects.filter(merchant=card.merchant, card=card).exists()


def test_theme_is_tenant_scoped(api_client, card):
    """Merchant B cannot touch merchant A's card theme."""
    other = factories.StaffUserFactory()  # a staff of a different merchant
    access = RefreshToken.for_user(other.user).access_token
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    resp = api_client.patch(
        f"/api/v1/cards/{card.id}/enroll-theme", {"accent_color": "#000000"}, format="json"
    )
    assert resp.status_code == 404


def test_qr_endpoint_returns_styled_svg(auth_client, card):
    RegistrationTheme.objects.create(
        merchant=card.merchant, card=None, qr_style={"module_style": "dots", "fg_color": "#654321"}
    )
    resp = auth_client.get(f"/api/v1/cards/{card.id}/qr")
    assert resp.status_code == 200
    body = resp.json()
    assert body["qr_svg"].startswith("<svg")
    assert "<circle" in body["qr_svg"] and "#654321" in body["qr_svg"]
