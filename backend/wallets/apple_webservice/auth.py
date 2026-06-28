"""Apple Wallet web-service auth (Apple's external spec).

Devices send ``Authorization: ApplePass <authenticationToken>`` where the token
is the pass's ``CustomerCard.auth_token``. We match it constant-time against the
serial (= CustomerCard id).
"""

from __future__ import annotations

import secrets

from core.models import CustomerCard


def authenticate_pass(request, serial: str) -> CustomerCard | None:
    """Return the CustomerCard if the ApplePass token matches the serial."""
    header = request.META.get("HTTP_AUTHORIZATION", "")
    prefix = "ApplePass "
    if not header.startswith(prefix):
        return None
    token = header[len(prefix) :].strip()

    cc = CustomerCard.objects.filter(id=serial).first()
    if cc is None:
        return None
    if not secrets.compare_digest(token, cc.auth_token):
        return None
    return cc
