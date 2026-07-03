"""Poster orchestration (Phase 3).

Bridges the pure Pillow rendering in :mod:`branding.qr` to Django storage: pulls
the merchant's logo + cover out of the media store, composes the poster PDF, and
saves it under a **content-addressed** name so an unchanged card reuses the same
file while a theme/reward/logo edit produces a fresh one. Returns the absolute
``/media/...`` URL (served by Caddy in prod, Django under DEBUG).

All storage/PIL work is best-effort: the QR endpoint calls this in a ``try`` and
falls back to an empty ``poster_pdf_url`` if anything here raises (e.g. Pillow
missing), so the code SVG is never withheld because the poster failed.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from branding.qr import render_poster_pdf

if TYPE_CHECKING:
    from PIL.Image import Image
    from rest_framework.request import Request

    from core.models import Card, Merchant


def _load_media_image(url: str | None) -> Image | None:
    """Open an image stored under ``MEDIA_URL`` as a PIL Image; ``None`` if it is
    blank, external (not our media), or unreadable."""
    if not url:
        return None
    marker = settings.MEDIA_URL  # normalised to "/media/"
    idx = url.find(marker)
    if idx == -1:  # external/CDN URL — don't fetch over the network in-request
        return None
    path = url[idx + len(marker) :]
    try:
        from PIL import Image

        with default_storage.open(path, "rb") as fh:
            img = Image.open(fh)
            img.load()  # force a read while the file is open
            return img
    except Exception:
        return None


def _prune_old_posters(card_id: Any, keep: str) -> None:
    """Delete this card's stale posters (previous digests) so the media store
    doesn't grow unbounded as the theme/reward is edited. Best-effort."""
    prefix = f"card_{card_id}_"
    keep_base = keep.rsplit("/", 1)[-1]
    try:
        _dirs, files = default_storage.listdir("posters")
    except (FileNotFoundError, NotImplementedError):
        return
    for fname in files:
        if fname.startswith(prefix) and fname != keep_base:
            try:
                default_storage.delete(f"posters/{fname}")
            except Exception:
                pass


def build_and_store_poster(
    request: Request,
    merchant: Merchant,
    card: Card,
    theme: dict[str, Any],
    join_url: str,
) -> str:
    """Compose + store the card's poster PDF and return its absolute media URL."""
    # Fingerprint every input that changes the pixels so the name is stable while
    # they are and rotates when they aren't. Uses only the URL strings (cheap) —
    # the images themselves are loaded lazily on a cache miss below.
    fingerprint = "|".join(
        [
            join_url,
            card.reward_title or "",
            card.reward_description or "",
            json.dumps(theme.get("qr_style") or {}, sort_keys=True),
            theme.get("bg_color") or "",
            theme.get("accent_color") or "",
            theme.get("cover_image_url") or "",
            card.logo_url or merchant.logo_url or "",
        ]
    )
    digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16]
    name = f"posters/card_{card.id}_{digest}.pdf"

    if not default_storage.exists(name):
        # Only decode the logo/cover on a cache miss — on a hit the endpoint costs
        # just the fingerprint + one exists() stat, not two image decodes.
        logo = _load_media_image(card.logo_url or merchant.logo_url)
        cover = _load_media_image(theme.get("cover_image_url"))
        pdf = render_poster_pdf(
            join_url,
            theme,
            reward_title=card.reward_title or "",
            reward_description=card.reward_description or "",
            logo=logo,
            cover=cover,
        )
        # FileSystemStorage.save won't overwrite; if a concurrent request already
        # wrote `name`, it lands under a suffixed name and we still return `name`,
        # which that other request created (identical bytes).
        default_storage.save(name, ContentFile(pdf))
        _prune_old_posters(card.id, keep=name)

    return request.build_absolute_uri(settings.MEDIA_URL + name)
