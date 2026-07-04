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

_RGB = tuple[int, int, int]


class AppleSigningError(RuntimeError):
    pass


def _hex_to_rgb(value: str | None, default: _RGB) -> _RGB:
    text = (value or "").lstrip("#")
    if len(text) != 6:
        return default
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError:
        return default


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

    def _from_logo(w: int, h: int) -> bytes | None:
        if not logo_bytes:
            return None
        try:
            src = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
            src.thumbnail((w, h))
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
        from_logo = _from_logo(w, h)
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
    from core.enums import CardType

    if card.type == CardType.STAMP and card.stamps_required > 0:
        base = _render_stamp_strip(
            customer_card.stamp_count, card.stamps_required, bg, fg, (1125, 369)
        )
        images["strip@3x.png"] = _png(base)
        images["strip@2x.png"] = _png(base.resize((750, 246), Image.Resampling.LANCZOS))
        images["strip.png"] = _png(base.resize((375, 123), Image.Resampling.LANCZOS))

    return images


def _render_stamp_strip(
    earned: int, required: int, bg: _RGB, fg: _RGB, size: tuple[int, int]
):  # type: ignore[no-untyped-def]
    """Draw the stamp grid on a brand-color strip (earned filled, remaining outline)."""
    from PIL import Image, ImageDraw

    w, h = size
    canvas = Image.new("RGBA", (w, h), (*bg, 255))
    draw = ImageDraw.Draw(canvas)

    n = max(1, min(required, 15))  # cap so a big card doesn't render dust
    earned = max(0, min(earned, n))
    rows = 1 if n <= 5 else 2
    cols = (n + rows - 1) // rows
    pad_x, pad_y = int(w * 0.06), int(h * 0.14)
    cell_w = (w - 2 * pad_x) / cols
    cell_h = (h - 2 * pad_y) / rows
    radius = int(min(cell_w, cell_h) * 0.34)
    ring = max(4, radius // 7)

    for i in range(n):
        r, c = divmod(i, cols)
        # centre the last row if it is short
        in_row = cols if r < rows - 1 else n - cols * (rows - 1)
        row_w = in_row * cell_w
        x0 = (w - row_w) / 2 + c * cell_w + cell_w / 2
        cy = pad_y + r * cell_h + cell_h / 2
        box = [x0 - radius, cy - radius, x0 + radius, cy + radius]
        if i < earned:
            draw.ellipse(box, fill=(*fg, 255))  # earned = solid
        else:
            draw.ellipse(box, outline=(*fg, 150), width=ring)  # remaining = ring
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
