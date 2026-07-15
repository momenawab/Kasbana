"""Build and sign a ``.pkpass`` bundle (contract §1: cryptography/openssl).

A .pkpass is a zip of: pass.json, the image assets, manifest.json (SHA-1 of
every file), and ``signature`` (a detached PKCS#7 signature of manifest.json
made with the Apple pass-signing certificate + the WWDR intermediate).
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile

from django.conf import settings

from core.models import CustomerCard
from wallets.apple.config import SigningMaterial, load_signing_material
from wallets.apple.passdata import build_pass_json
from wallets.stamp_grid import LAYOUT_GRID as _LAYOUT_GRID
from wallets.stamp_grid import darken as _darken
from wallets.stamp_grid import hex_to_rgb as _hex_to_rgb
from wallets.stamp_grid import render_stamp_grid as _render_stamp_strip

_RGB = tuple[int, int, int]


class AppleSigningError(RuntimeError):
    pass


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


def _font(size: int):  # type: ignore[no-untyped-def]
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - very old Pillow
        return ImageFont.load_default()


def build_pass_images(customer_card: CustomerCard) -> dict[str, bytes]:
    """Render the pkpass image assets at Apple's required sizes.

    iOS rejects a pass whose ``icon.png`` is not a real image (a 1x1 placeholder
    makes Safari say "cannot download this file"). Uses the merchant/card logo
    when it is a local upload; otherwise a branded fallback (brand color + the
    merchant's initial for the icon, merchant name for the logo).
    """
    from PIL import Image, ImageDraw

    card = customer_card.card
    merchant = card.merchant
    name = (merchant.name or "").strip()
    bg = _hex_to_rgb(card.color_bg or merchant.color_bg, (11, 122, 91))
    fg = _hex_to_rgb(card.color_fg or merchant.color_fg, (255, 255, 255))
    logo_bytes = _local_media_bytes(card.logo_url or merchant.logo_url)

    def _png(img: Image.Image) -> bytes:
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()

    def _from_logo(w: int, h: int, align: str = "center") -> bytes | None:
        if not logo_bytes:
            return None
        try:
            src = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
            # Trim fully-transparent padding baked into the source PNG so the mark
            # sits flush against the edge instead of floating inside its own
            # whitespace (this is what made the logo look indented on the pass).
            bbox = src.getbbox()
            if bbox:
                src = src.crop(bbox)
            src.thumbnail((w, h))
            if align == "left":
                # Size the canvas to the mark's real width (not the full 160px
                # slot) so Apple renders logoText immediately after it — otherwise
                # the business name is pushed to the middle by the empty canvas.
                canvas = Image.new("RGBA", (src.width or 1, h), (0, 0, 0, 0))
                canvas.paste(src, (0, (h - src.height) // 2), src)
            else:
                # Square icon: keep the mark centred in the full slot.
                canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                canvas.paste(src, ((w - src.width) // 2, (h - src.height) // 2), src)
            return _png(canvas)
        except Exception:  # pragma: no cover - bad image bytes
            return None

    def _icon(size: int) -> bytes:
        from_logo = _from_logo(size, size)
        if from_logo is not None:
            return from_logo
        canvas = Image.new("RGBA", (size, size), (*bg, 255))
        draw = ImageDraw.Draw(canvas)
        letter = (name[:1] or "•").upper()
        font = _font(int(size * 0.6))
        left, top, right, bottom = draw.textbbox((0, 0), letter, font=font)
        draw.text(
            ((size - (right - left)) / 2 - left, (size - (bottom - top)) / 2 - top),
            letter,
            font=font,
            fill=(*fg, 255),
        )
        return _png(canvas)

    def _logo(w: int, h: int) -> bytes:
        from_logo = _from_logo(w, h, align="left")
        if from_logo is not None:
            return from_logo
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        text = (name[:18] or "Loyalty").strip()
        font = _font(int(h * 0.6))
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        draw.text((0, (h - (bottom - top)) / 2 - top), text, font=font, fill=(*fg, 255))
        return _png(canvas)

    images: dict[str, bytes] = {
        "icon.png": _icon(29),
        "icon@2x.png": _icon(58),
        "icon@3x.png": _icon(87),
        "logo.png": _logo(160, 50),
        "logo@2x.png": _logo(320, 100),
    }

    # STAMP cards get a strip image with a stamp grid (earned filled, remaining
    # outlined) — the coffee-card look. Points cards have no grid, so no strip.
    # A merchant can turn the strip off, or supply custom empty/filled stamp
    # icons that get tiled in place of the drawn circles (notes 2-4).
    #
    # Templates pin the strip to their ``bottom_visual``: ``stamps`` → the stamp
    # grid, ``image`` → the uploaded bottom image (letterboxed on the strip band).
    from core.enums import CardType
    from wallets import design as design_mod

    design = design_mod.get_design(card)
    template = design_mod.template_for(card)
    if template is not None:
        bottom_visual = template.get("bottom_visual", "none")
        strip_on = bottom_visual in ("stamps", "image")
    else:
        strip_on = card.type == CardType.STAMP and card.stamps_required > 0
        if design is not None:
            strip_on = strip_on and design.apple_strip_enabled
    if strip_on:
        from wallets import stamp_icons

        empty_icon = _local_media_bytes(design.strip_empty_url) if design else None
        filled_icon = _local_media_bytes(design.strip_filled_url) if design else None
        # A built-in stamp icon (tinted with stamp_color) fills in when no custom
        # pair is uploaded; stamp_color also recolors the drawn circles/fg.
        fg, empty_icon, filled_icon = stamp_icons.resolve_stamp_render(
            design, fg, empty_icon, filled_icon
        )
        # Give the strip its own band background so the stamps don't blend into
        # the pass: the merchant's strip color, else a slightly darkened brand bg.
        strip_bg = (
            _hex_to_rgb(design.strip_bg_color, bg)
            if (design and design.strip_bg_color)
            else _darken(bg)
        )
        if template is not None and bottom_visual == "image":
            base = _render_bottom_image_strip(
                design.bottom_image_url if design else "", strip_bg, (1125, 369)
            )
        else:
            base = _render_stamp_strip(
                customer_card.stamp_count,
                card.stamps_required,
                strip_bg,
                fg,
                (1125, 369),
                empty_icon=empty_icon,
                filled_icon=filled_icon,
                layout=(design.stamp_layout if design else "") or _LAYOUT_GRID,
            )
        images["strip@3x.png"] = _png(base)
        images["strip@2x.png"] = _png(base.resize((750, 246), Image.Resampling.LANCZOS))
        images["strip.png"] = _png(base.resize((375, 123), Image.Resampling.LANCZOS))

    # The platform ("Powered by") branding is rendered as Apple ``logoText`` beside
    # the top-left brand logo (see wallets.apple.passdata) — Apple store cards have
    # no right-side image slot, and nothing may sit below the barcode, so there is
    # no footer.png image here.

    return images


def _render_bottom_image_strip(url: str, bg: _RGB, size: tuple[int, int]):  # type: ignore[no-untyped-def]
    """Letterbox a merchant's bottom image into the Apple strip band.

    The image is fit (preserving aspect) and centred on the strip background so
    a missing/odd-aspect image still yields a valid band rather than a crash.
    """
    from PIL import Image

    w, h = size
    canvas = Image.new("RGBA", (w, h), (*bg, 255))
    data = _local_media_bytes(url)
    if not data:
        return canvas
    try:
        src = Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:  # pragma: no cover - bad image bytes
        return canvas
    src.thumbnail((w, h))
    canvas.paste(src, ((w - src.width) // 2, (h - src.height) // 2), src)
    return canvas


def digest_dict(files: dict[str, bytes]) -> dict[str, str]:
    return {name: hashlib.sha1(data).hexdigest() for name, data in files.items()}


def _sign_manifest(manifest: bytes, material: SigningMaterial) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.serialization import Encoding, pkcs7

    builder = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(manifest)
        .add_signer(material.cert, material.key, hashes.SHA256())
    )
    if material.wwdr is not None:
        builder = builder.add_certificate(material.wwdr)
    # Apple's reference (signpass = `openssl smime -binary -sign`, WITHOUT
    # -noattr) signs WITH authenticated attributes — content-type, message-digest
    # and signing-time. iOS PassKit requires them; a NoAttributes signature still
    # passes `openssl smime -verify` but iOS rejects the pass ("Safari cannot
    # download this file"). Binary avoids S/MIME CRLF canonicalisation of the
    # manifest so the message-digest matches the raw bytes on disk.
    options = [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary]
    return builder.sign(Encoding.DER, options)


def build_pkpass(customer_card: CustomerCard, material: SigningMaterial | None = None) -> bytes:
    """Return the signed .pkpass bytes. Raises AppleSigningError if no certs."""
    material = material or load_signing_material()
    if material is None:
        raise AppleSigningError("Apple signing material is not configured.")

    pass_json = json.dumps(build_pass_json(customer_card), separators=(",", ":")).encode()

    files: dict[str, bytes] = {"pass.json": pass_json, **build_pass_images(customer_card)}
    manifest = json.dumps(digest_dict(files), separators=(",", ":")).encode()
    signature = _sign_manifest(manifest, material)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
        zf.writestr("manifest.json", manifest)
        zf.writestr("signature", signature)
    return buf.getvalue()
