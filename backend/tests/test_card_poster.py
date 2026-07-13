"""Tests for the styled-PNG + poster-PDF QR assets (Phase 3).

Covers the ``GET /cards/{id}/qr`` poster wiring (poster_pdf_url populated, file
written to media, stable across calls), graceful degradation when poster
rendering fails, and the pure Pillow renderers in ``branding.qr``.
"""

from __future__ import annotations

import pytest

from tests import factories

pytestmark = pytest.mark.django_db


def _storage_path(url: str) -> str:
    from django.conf import settings

    return url.split(settings.MEDIA_URL, 1)[1]


def test_qr_endpoint_populates_poster_url(auth_client, merchant, settings, tmpdir):
    from django.core.files.storage import default_storage

    settings.MEDIA_ROOT = str(tmpdir)
    card = factories.CardFactory(merchant=merchant, reward_title="Free coffee")

    body = auth_client.get(f"/api/v1/cards/{card.id}/qr").json()
    assert body["qr_svg"].startswith("<svg")
    url = body["poster_pdf_url"]
    assert url.endswith(".pdf")
    assert f"posters/card_{card.id}_" in url

    # The PDF was actually written to media and is a real PDF.
    path = _storage_path(url)
    assert default_storage.exists(path)
    with default_storage.open(path, "rb") as fh:
        assert fh.read(5) == b"%PDF-"


def test_poster_url_is_stable_across_calls(auth_client, merchant, settings, tmpdir):
    settings.MEDIA_ROOT = str(tmpdir)
    card = factories.CardFactory(merchant=merchant, reward_title="Free coffee")

    first = auth_client.get(f"/api/v1/cards/{card.id}/qr").json()["poster_pdf_url"]
    second = auth_client.get(f"/api/v1/cards/{card.id}/qr").json()["poster_pdf_url"]
    # Content-addressed name -> identical URL, and only one file on disk.
    assert first == second
    import os

    posters_dir = os.path.join(str(tmpdir), "posters")
    assert len(os.listdir(posters_dir)) == 1


def test_editing_card_prunes_the_stale_poster(auth_client, merchant, settings, tmpdir):
    import os

    settings.MEDIA_ROOT = str(tmpdir)
    card = factories.CardFactory(merchant=merchant, reward_title="Free coffee")

    first = auth_client.get(f"/api/v1/cards/{card.id}/qr").json()["poster_pdf_url"]

    # A reward edit changes the fingerprint -> a new poster; the old one is pruned
    # so the media store doesn't accumulate a file per edit.
    card.reward_title = "Free latte"
    card.save(update_fields=["reward_title"])
    second = auth_client.get(f"/api/v1/cards/{card.id}/qr").json()["poster_pdf_url"]

    assert first != second
    assert len(os.listdir(os.path.join(str(tmpdir), "posters"))) == 1


def test_qr_endpoint_survives_poster_failure(auth_client, merchant, settings, tmpdir, monkeypatch):
    settings.MEDIA_ROOT = str(tmpdir)
    card = factories.CardFactory(merchant=merchant, reward_title="Free coffee")

    # A poster rendering blow-up must not withhold the inline SVG or 500.
    import branding.poster as poster

    def boom(*_a, **_k):
        raise RuntimeError("pillow exploded")

    monkeypatch.setattr(poster, "render_poster_pdf", boom)

    resp = auth_client.get(f"/api/v1/cards/{card.id}/qr")
    assert resp.status_code == 200
    body = resp.json()
    assert body["qr_svg"].startswith("<svg")
    assert body["poster_pdf_url"] == ""


# ── Pure renderers ────────────────────────────────────────────────────────────
def test_render_qr_png_shapes_and_logo():
    from PIL import Image

    from branding.qr import render_qr_png

    img = render_qr_png("https://x/enroll/abc", {"module_style": "dots", "fg_color": "#0a7"})
    assert img.mode == "RGB" and img.size[0] > 0

    logo = Image.new("RGB", (48, 48), (200, 30, 30))
    with_logo = render_qr_png("https://x/enroll/abc", {"module_style": "rounded"}, logo=logo)
    assert with_logo.size[0] > 0


def test_render_poster_pdf_is_pdf():
    from branding.qr import render_poster_pdf

    pdf = render_poster_pdf(
        "https://x/enroll/abc",
        {"bg_color": "#ffffff", "accent_color": "#0a7733", "qr_style": {"module_style": "square"}},
        reward_title="Free coffee",
        reward_description="After 8 stamps",
    )
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1000


def test_poster_always_stamps_powered_by(monkeypatch):
    # The mark is mandatory on every plan. The copy is rasterised into the PDF,
    # so assert on what gets drawn rather than grepping the bytes.
    import branding.qr as qr

    drawn: list[str] = []
    original = qr._draw_centered

    def record(draw, text, y, width, font, fill):  # noqa: ANN001
        drawn.append(text)
        return original(draw, text, y, width, font, fill)

    monkeypatch.setattr(qr, "_draw_centered", record)
    qr.render_poster_pdf(
        "https://x/enroll/abc",
        {"bg_color": "#101010", "qr_style": {"module_style": "square"}},
        reward_title="Free coffee",
    )
    assert qr.POWERED_BY in drawn
