"""Google Wallet stamp-hero banner (visual stamp counter).

Google has no Apple-style strip, so to show a *visual* stamp counter we render
the stamp grid into a wide hero banner and set it as the loyalty object's
``heroImage``. Because Google caches images by URL, the banner is stored
**content-addressed** on (card, count, colors, icons): each stamp count gets a
distinct URL, so a PATCH to the new URL forces Google to fetch the fresh image.

All work is best-effort — a render/storage failure returns ``None`` so the pass
still updates its numeric balance.
"""

from __future__ import annotations

import hashlib
import io

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from core.models import CustomerCard
from wallets import design as design_mod
from wallets.stamp_grid import darken, hex_to_rgb, render_stamp_grid

# Google hero recommended ratio is wide (~1032x336).
_HERO_SIZE = (1032, 336)
_DIR = "google-hero"


def _local_media_bytes(url: str) -> bytes | None:
    """Read an uploaded image from local media by URL (no network / SSRF)."""
    if not url:
        return None
    key = "/" + str(settings.MEDIA_URL).strip("/") + "/"
    if key not in url:
        return None
    path = url.split(key, 1)[1]
    try:
        if default_storage.exists(path):
            with default_storage.open(path, "rb") as fh:
                return fh.read()
    except Exception:  # pragma: no cover - defensive
        return None
    return None


def is_stamp_hero_enabled(card) -> bool:  # type: ignore[no-untyped-def]
    from core.enums import CardType

    design = design_mod.get_design(card)
    return bool(
        design
        and design.google_stamp_hero
        and card.type == CardType.STAMP
        and card.stamps_required > 0
    )


def _prune_old(card_id: object, keep: str) -> None:
    """Drop this card's stale hero banners (previous counts/colors). Best-effort."""
    prefix = f"card_{card_id}_"
    keep_base = keep.rsplit("/", 1)[-1]
    try:
        _dirs, files = default_storage.listdir(_DIR)
    except (FileNotFoundError, NotImplementedError):
        return
    for fname in files:
        if fname.startswith(prefix) and fname != keep_base:
            try:
                default_storage.delete(f"{_DIR}/{fname}")
            except Exception:
                pass


def stamp_hero_url(customer_card: CustomerCard) -> str | None:
    """Render + store the stamp-hero banner and return its absolute media URL.

    ``None`` when the feature is off, the card isn't a stamp card, or anything in
    the render/store path fails. Content-addressed so an unchanged state reuses
    the file and a new stamp count produces a fresh URL Google will re-fetch.
    """
    card = customer_card.card
    if not is_stamp_hero_enabled(card):
        return None
    design = design_mod.get_design(card)
    try:
        merchant = card.merchant
        bg = hex_to_rgb(
            (design and design.strip_bg_color) or "",
            hex_to_rgb(card.color_bg or merchant.color_bg, darken((11, 122, 91))),
        )
        fg = hex_to_rgb(card.color_fg or merchant.color_fg, (255, 255, 255))
        empty_icon = _local_media_bytes(design.strip_empty_url) if design else None
        filled_icon = _local_media_bytes(design.strip_filled_url) if design else None

        fingerprint = "|".join(
            [
                str(customer_card.stamp_count),
                str(card.stamps_required),
                str(bg),
                str(fg),
                design.strip_empty_url if design else "",
                design.strip_filled_url if design else "",
            ]
        )
        digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16]
        name = f"{_DIR}/card_{card.id}_{digest}.png"

        if not default_storage.exists(name):
            img = render_stamp_grid(
                customer_card.stamp_count,
                card.stamps_required,
                bg,
                fg,
                _HERO_SIZE,
                empty_icon=empty_icon,
                filled_icon=filled_icon,
            )
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            default_storage.save(name, ContentFile(buf.getvalue()))
            _prune_old(card.id, keep=name)

        base = str(settings.BASE_URL or "").rstrip("/")
        return f"{base}{settings.MEDIA_URL}{name}"
    except Exception:  # pragma: no cover - best-effort
        return None
