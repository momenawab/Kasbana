"""Platform (Kasbana) watermark — the "Powered by" branding on a pass.

* **Apple** → the platform brand rides as ``logoText`` beside the top-left logo
  (see ``wallets.apple.passdata``); Apple store cards have no right-side image
  slot and nothing may sit below the barcode, so there is no footer image.
* **Google** → composited into the bottom-right corner of the hero banner when a
  hero is generated (Google has no footer slot). ``apply_watermark`` below.

The real asset is configured via ``settings.WALLET_PLATFORM_LOGO_URL`` (a local
``/uploads`` URL — read with no SSRF). Until the real logo exists this renders a
drawn **PLACEHOLDER** badge, so the slot is visibly wired and ready to swap.

All rendering is best-effort: any failure returns ``None``/the unmodified image
so it can never break or withhold a pass.
"""

from __future__ import annotations

import io
import os

from django.conf import settings

_RGB = tuple[int, int, int]

# Bundled platform lockup (the Stampn mark + "Stampn" wordmark, white with a
# soft shadow so it reads on light or dark heroes). Used as the fallback when
# WALLET_PLATFORM_LOGO_URL isn't configured, so the real "logo + name" renders
# out of the box — no env/upload.
_BUNDLED_LOGO = os.path.join(os.path.dirname(__file__), "static", "wallet", "platform-logo.png")


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


def _bundled_logo_bytes() -> bytes | None:
    """The self-hosted platform logo shipped in ``wallets/static/wallet``."""
    try:
        with open(_BUNDLED_LOGO, "rb") as fh:
            return fh.read()
    except OSError:  # pragma: no cover - missing bundled asset
        return None


def platform_logo_bytes() -> bytes | None:
    """Platform logo bytes: the configured ``WALLET_PLATFORM_LOGO_URL`` upload if
    set, otherwise the bundled brand logo. ``None`` only if neither is readable
    (→ draw the placeholder)."""
    return _local_media_bytes(getattr(settings, "WALLET_PLATFORM_LOGO_URL", "")) or (
        _bundled_logo_bytes()
    )


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


def apply_watermark(hero, fg: _RGB):  # type: ignore[no-untyped-def]
    """Paste the platform logo (or placeholder) at the bottom-right of ``hero``.

    Returns ``hero`` (modified in place). Used by the Google hero renderer so
    the bottom-right branding appears on the generated banner image.
    """
    try:
        from PIL import Image, ImageFilter

        w, h = hero.size
        target_h = int(h * 0.34)
        logo = _decode(platform_logo_bytes())
        if logo is None:
            logo = _placeholder((max(target_h * 2, target_h + 24), target_h), fg)
        else:
            # Trim transparent padding so the logo sits flush in the corner.
            bbox = logo.getbbox()
            if bbox:
                logo = logo.crop(bbox)
            logo.thumbnail((w // 3, target_h))
        pad = max(8, h // 28)
        x, y = w - logo.width - pad, h - logo.height - pad
        # Soft shadow behind the logo so a light/white wordmark stays legible on
        # light heroes (it's invisible on dark ones).
        shadow = Image.new("RGBA", logo.size, (0, 0, 0, 0))
        shadow.paste(Image.new("RGBA", logo.size, (0, 0, 0, 165)), (0, 0), logo.split()[3])
        shadow = shadow.filter(ImageFilter.GaussianBlur(max(2, logo.height // 18)))
        hero.paste(shadow, (x, y + 2), shadow)
        hero.paste(logo, (x, y), logo)
        return hero
    except Exception:  # pragma: no cover - best-effort
        return hero
