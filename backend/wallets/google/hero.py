"""Google Wallet hero banner (visual stamp counter / bottom image).

Google has no Apple-style strip, so to show a *visual* stamp counter we render
the stamp grid into a wide hero banner and set it as the loyalty object's
``heroImage``. Because Google caches images by URL, the banner is stored
**content-addressed** on (card, count, colors, icons): each stamp count gets a
distinct URL, so a PATCH to the new URL forces Google to fetch the fresh image.

Image-style templates do the same with the merchant's bottom image (static,
content-addressed on the image URL). The platform (Kasbana) watermark is
composited at the bottom-right of every banner.

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
from wallets.platform_logo import apply_watermark
from wallets.stamp_grid import LAYOUT_GRID, darken, hex_to_rgb, render_stamp_grid

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


def _stamp_card_ready(card) -> bool:  # type: ignore[no-untyped-def]
    """A stamp card with a goal — the minimum for a stamp-grid hero."""
    from core.enums import CardType

    return card.type == CardType.STAMP and card.stamps_required > 0


def _stamp_colors(card, design) -> tuple[tuple[int, int, int], tuple[int, int, int]]:  # type: ignore[no-untyped-def]
    merchant = card.merchant
    bg = hex_to_rgb(
        (design and design.strip_bg_color) or "",
        hex_to_rgb(card.color_bg or merchant.color_bg, darken((11, 122, 91))),
    )
    fg = hex_to_rgb(card.color_fg or merchant.color_fg, (255, 255, 255))
    return bg, fg


def _media_url(name: str) -> str:
    base = str(settings.BASE_URL or "").rstrip("/")
    return f"{base}{settings.MEDIA_URL}{name}"


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


def stamp_hero_url(customer_card: CustomerCard, *, force: bool = False) -> str | None:
    """Render + store the stamp-hero banner and return its absolute media URL.

    ``None`` when the feature is off, the card isn't a stamp card, or anything in
    the render/store path fails. Content-addressed so an unchanged state reuses
    the file and a new stamp count produces a fresh URL Google will re-fetch.

    ``force`` skips the ``google_stamp_hero`` toggle (used by stamps templates,
    where the layout is locked and the counter is always the bottom visual).
    """
    card = customer_card.card
    if force:
        if not _stamp_card_ready(card):
            return None
    elif not is_stamp_hero_enabled(card):
        return None
    design = design_mod.get_design(card)
    try:
        from wallets import stamp_icons

        bg, fg = _stamp_colors(card, design)
        empty_icon = _local_media_bytes(design.strip_empty_url) if design else None
        filled_icon = _local_media_bytes(design.strip_filled_url) if design else None
        # Built-in stamp icon (tinted with stamp_color) fills in when no custom
        # pair is uploaded; stamp_color also recolors the drawn circles/fg.
        fg, empty_icon, filled_icon = stamp_icons.resolve_stamp_render(
            design, fg, empty_icon, filled_icon
        )

        # Content-address on everything that changes the pixels so a new icon,
        # color, or count produces a fresh URL Google will re-fetch.
        fingerprint = "|".join(
            [
                str(customer_card.stamp_count),
                str(card.stamps_required),
                str(bg),
                str(fg),
                design.strip_empty_url if design else "",
                design.strip_filled_url if design else "",
                design.stamp_icon if design else "",
                design.stamp_color if design else "",
                # Without this a layout change would hash to the SAME name, and
                # Google would keep serving the cached hero — the edit would look
                # like it silently did nothing.
                design.stamp_layout if design else "",
                # Same trap for the strip artwork and the stamps-visible toggle:
                # both change the pixels, so both must change the digest.
                design.strip_bg_image_url if design else "",
                str(design.strip_stamps_visible) if design else "",
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
                layout=(design.stamp_layout if design else "") or LAYOUT_GRID,
                # The same upload as the Apple strip, cover-cropped to the hero's
                # own (narrower) ratio rather than distorted to fit it.
                background=_local_media_bytes(design.strip_bg_image_url) if design else None,
                stamps_visible=(design.strip_stamps_visible if design else True),
            )
            # Platform watermark at the bottom-right of the banner.
            img = apply_watermark(img, fg)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            default_storage.save(name, ContentFile(buf.getvalue()))
            _prune_old(card.id, keep=name)

        return _media_url(name)
    except Exception:  # pragma: no cover - best-effort
        return None


def bottom_image_hero_url(customer_card: CustomerCard) -> str | None:
    """Store the merchant's bottom image as a static Google hero, watermarked.

    Content-addressed on the image URL (not the stamp count) so every card with
    the same image reuses one file. ``None`` when no image is set or storage
    fails. Used by image-style templates.
    """
    card = customer_card.card
    design = design_mod.get_design(card)
    url = design.bottom_image_url if design else ""
    data = _local_media_bytes(url)
    if not data:
        return None
    try:
        from PIL import Image

        bg, fg = _stamp_colors(card, design)
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        name = f"{_DIR}/img_{card.id}_{digest}.png"
        if not default_storage.exists(name):
            canvas = Image.new("RGBA", _HERO_SIZE, (*bg, 255))
            try:
                src = Image.open(io.BytesIO(data)).convert("RGBA")
                src.thumbnail(_HERO_SIZE)
                canvas.paste(
                    src,
                    ((_HERO_SIZE[0] - src.width) // 2, (_HERO_SIZE[1] - src.height) // 2),
                    src,
                )
            except Exception:  # pragma: no cover - bad image bytes
                pass
            canvas = apply_watermark(canvas, fg)
            buf = io.BytesIO()
            canvas.convert("RGB").save(buf, format="PNG")
            default_storage.save(name, ContentFile(buf.getvalue()))
        return _media_url(name)
    except Exception:  # pragma: no cover - best-effort
        return None


def hero_url_for(customer_card: CustomerCard) -> str | None:
    """The hero banner for a card, template-aware.

    * freeform → respects the ``google_stamp_hero`` toggle (unchanged).
    * stamps template → the stamp grid, refreshed per count (forced on).
    * image template → the merchant bottom image (static, watermarked).
    * none template → no hero.
    """
    template = design_mod.template_for(customer_card.card)
    if template is None:
        return stamp_hero_url(customer_card)
    visual = template.get("bottom_visual", "none")
    if visual == "stamps":
        return stamp_hero_url(customer_card, force=True)
    if visual == "image":
        return bottom_image_hero_url(customer_card)
    return None
