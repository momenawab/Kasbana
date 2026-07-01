"""Build and sign a ``.pkpass`` bundle (contract §1: cryptography/openssl).

A .pkpass is a zip of: pass.json, the image assets, manifest.json (SHA-1 of
every file), and ``signature`` (a detached PKCS#7 signature of manifest.json
made with the Apple pass-signing certificate + the WWDR intermediate).
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile

from core.models import CustomerCard
from wallets.apple.config import SigningMaterial, load_signing_material
from wallets.apple.passdata import build_pass_json

# Minimal 1x1 PNG used as a placeholder icon/logo so the bundle is structurally
# complete. Replace with branded assets (e.g. from logo_url) in production.
_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC"
)


class AppleSigningError(RuntimeError):
    pass


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
    options = [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.NoAttributes]
    return builder.sign(Encoding.DER, options)


def build_pkpass(customer_card: CustomerCard, material: SigningMaterial | None = None) -> bytes:
    """Return the signed .pkpass bytes. Raises AppleSigningError if no certs."""
    material = material or load_signing_material()
    if material is None:
        raise AppleSigningError("Apple signing material is not configured.")

    pass_json = json.dumps(build_pass_json(customer_card), separators=(",", ":")).encode()

    files: dict[str, bytes] = {
        "pass.json": pass_json,
        "icon.png": _PLACEHOLDER_PNG,
        "icon@2x.png": _PLACEHOLDER_PNG,
        "logo.png": _PLACEHOLDER_PNG,
    }
    manifest = json.dumps(digest_dict(files), separators=(",", ":")).encode()
    signature = _sign_manifest(manifest, material)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
        zf.writestr("manifest.json", manifest)
        zf.writestr("signature", signature)
    return buf.getvalue()
