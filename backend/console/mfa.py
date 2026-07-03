"""TOTP MFA helpers for the admin console (Phase 15).

Thin wrappers around ``pyotp`` so the views stay declarative. The QR is rendered
as an SVG data-URI (no Pillow dependency) that the enrollment screen shows for a
one-tap scan into any authenticator app.
"""

from __future__ import annotations

import base64
import io

import pyotp
import qrcode
import qrcode.image.svg

ISSUER = "Stampn Admin"


def new_secret() -> str:
    """A fresh base32 TOTP seed."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    """The ``otpauth://`` URI an authenticator app imports."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def qr_data_uri(otpauth_uri: str) -> str:
    """An ``data:image/svg+xml`` QR of the provisioning URI (Pillow-free)."""
    img = qrcode.make(otpauth_uri, image_factory=qrcode.image.svg.SvgImage)
    buf = io.BytesIO()
    img.save(buf)
    encoded = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/svg+xml;base64,{encoded}"


def verify(secret: str, code: str) -> bool:
    """Check a 6-digit TOTP code, tolerating one step of clock drift."""
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
