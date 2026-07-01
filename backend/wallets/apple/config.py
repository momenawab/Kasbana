"""Apple Wallet configuration + signing-material loading (contract §3.8).

Reads ``WALLET["APPLE"]`` (pass-type id, team id, the pass-signing .p12, the
WWDR intermediate cert, APNs sandbox flag). When certs are absent the backend
degrades to no-op so the rest of the app keeps working in local/dev.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, cast

from django.conf import settings


def _apple() -> dict[str, Any]:
    return cast("dict[str, Any]", settings.WALLET["APPLE"])


def pass_type_id() -> str:
    return _apple().get("PASS_TYPE_ID", "")


def team_id() -> str:
    return _apple().get("TEAM_ID", "")


def apns_use_sandbox() -> bool:
    return bool(_apple().get("APNS_USE_SANDBOX", False))


@dataclass
class SigningMaterial:
    key: Any  # private key
    cert: Any  # signing certificate (x509)
    wwdr: Any | None  # WWDR intermediate (x509) or None


def load_signing_material() -> SigningMaterial | None:
    """Load the pass-signing key + cert (+ WWDR) from disk, or ``None``."""
    p12_path = _apple().get("PASS_CERT_PATH", "")
    if not p12_path or not os.path.exists(p12_path):
        return None

    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import pkcs12

    password = _apple().get("PASS_CERT_PASSWORD", "") or ""
    with open(p12_path, "rb") as fh:
        key, cert, _add = pkcs12.load_key_and_certificates(fh.read(), password.encode() or None)
    if key is None or cert is None:
        return None

    wwdr = None
    wwdr_path = _apple().get("WWDR_CERT_PATH", "")
    if wwdr_path and os.path.exists(wwdr_path):
        with open(wwdr_path, "rb") as fh:
            wwdr = x509.load_pem_x509_certificate(fh.read())

    return SigningMaterial(key=key, cert=cert, wwdr=wwdr)


def is_configured() -> bool:
    return bool(team_id()) and bool(pass_type_id()) and load_signing_material() is not None
