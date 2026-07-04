"""Platform (Kasbana) watermark/logo — the bottom-left "Powered by" slot.

Every wallet pass carries a small platform logo at the bottom-left:

* **Apple** → rendered into ``footer.png`` (Apple's native bottom-of-pass slot,
  shown left-aligned just above the barcode).
* **Google** → composited into the bottom-left corner of the hero banner when a
  hero is generated (Google has no footer slot).

The real asset is configured via ``settings.WALLET_PLATFORM_LOGO_URL`` (a local
``/uploads`` URL — read with no SSRF). Until the real logo exists this renders a
drawn **PLACEHOLDER** badge, so the slot is visibly wired and ready to swap.

All rendering is best-effort: any failure returns ``None``/the unmodified image
so it can never break or withhold a pass.
"""

from __future__ import annotations

import io

from django.conf import settings

_RGB = tuple[int, int, int]


def _local_media_bytes(url: str) -> bytes | None:
    """Read an uploaded image from local media by URL (no network / SSRF)."""
    if not url:
        return None
    key = "/" + str(settings.MEDIA_URL).strip("/") + "/"
    if key not in url:
        return None
    path = url.split(key, 1)[1]
    try:
        from django.core.files.storage import default_storage

        if default_storage.exists(path):
            with default_storage.open(path, "rb") as fh:
                return fh.read()
    except Exception:  # pragma: no cover - defensive
        return None
    return None


def platform_logo_bytes() -> bytes | None:
    """Configured platform logo bytes, or ``None`` (→ draw the placeholder)."""
    return _local_media_bytes(getattr(settings, "WALLET_PLATFORM_LOGO_URL", ""))


def _decode(data: bytes | None):  # type: ignore[no-untyped-def]
    if not data:
        return None
    try:
        from PIL import Image

        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:  # pragma: no cover - bad image bytes
        return None


def _font(size: int):  # type: ignore[no-untyped-def]
    try:
        from PIL import ImageFont

        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - very old Pillow
        from PIL import ImageFont

        return ImageFont.load_default()


def _placeholder(size: tuple[int, int], fg: _RGB, label: str = "LOGO"):  # type: ignore[no-untyped-def]
    """A drawn placeholder badge (used until the real platform logo is set)."""
    from PIL import Image, ImageDraw

    w, h = size
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    # A subtle filled pill so the slot is visibly "there", ready to replace.
    draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=max(2, h // 4), fill=(*fg, 60))
    font = _font(max(8, int(h * 0.55)))
    left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
    draw.text(
        ((w - (right - left)) / 2 - left, (h - (bottom - top)) / 2 - top),
        label,
        font=font,
        fill=(*fg, 220),
    )
    return canvas


def render_footer(size: tuple[int, int], fg: _RGB):  # type: ignore[no-untyped-def]
    """Apple ``footer.png`` image: the platform logo at the bottom-left.

    A transparent canvas with the logo (or placeholder) left-aligned and
    vertically centred. ``None`` only if PIL is unavailable (caller falls back
    to no footer).
    """
    from PIL import Image

    w, h = size
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    target_h = int(h * 0.82)
    logo = _decode(platform_logo_bytes())
    if logo is None:
        # Placeholder keeps aspect ~3:1 so the "LOGO" reads.
        logo = _placeholder((max(target_h * 2, target_h + 24), target_h), fg)
    else:
        logo.thumbnail((w, target_h))
    canvas.paste(logo, (0, (h - logo.height) // 2), logo)
    return canvas


def apply_watermark(hero, fg: _RGB):  # type: ignore[no-untyped-def]
    """Paste the platform logo (or placeholder) at the bottom-left of ``hero``.

    Returns ``hero`` (modified in place). Used by the Google hero renderer so
    the bottom-left branding appears on the generated banner image.
    """
    try:
        w, h = hero.size
        target_h = int(h * 0.34)
        logo = _decode(platform_logo_bytes())
        if logo is None:
            logo = _placeholder((max(target_h * 2, target_h + 24), target_h), fg)
        else:
            logo.thumbnail((w // 3, target_h))
        pad = max(8, h // 28)
        hero.paste(logo, (pad, h - logo.height - pad), logo)
        return hero
    except Exception:  # pragma: no cover - best-effort
        return hero
