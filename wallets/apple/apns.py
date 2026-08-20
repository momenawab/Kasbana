"""APNs empty-payload push for Apple Wallet pass updates (contract §1: httpx HTTP/2).

A pass update is signalled by an *empty* push to each registered device's push
token, using the pass-type certificate for TLS client auth over APNs HTTP/2.
The device then calls the web service to pull the refreshed pass.
"""

from __future__ import annotations

import logging
import ssl
import tempfile
import time

import httpx

from wallets.apple.config import apns_use_sandbox, load_signing_material, pass_type_id

logger = logging.getLogger(__name__)

_PROD = "https://api.push.apple.com"
_SANDBOX = "https://api.sandbox.push.apple.com"

# How long APNs should keep trying to deliver a pass-update push if the device
# is offline/locked (seconds). Without an expiration, APNs treats the push as
# expire-on-first-attempt and silently drops it for an unreachable device — so a
# customer whose phone was asleep would only see the update on the *next* refresh
# trigger (the "message is delayed" symptom, note 5). One hour of store-and-retry
# lets a phone that comes back online shortly after still pull the fresh pass.
# (This does not defeat iOS's own background-refresh throttling, which is
# Apple-side and outside our control.)
_APNS_EXPIRATION_WINDOW = 3600


def _client_ssl_context() -> ssl.SSLContext | None:
    """Build an SSL context using the pass cert/key for APNs client auth."""
    material = load_signing_material()
    if material is None:
        return None
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        pkcs12,  # noqa: F401
    )

    cert_pem = material.cert.public_bytes(Encoding.PEM)
    key_pem = material.key.private_bytes(
        Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
    )
    # SSLContext.load_cert_chain needs files; write to a temp combined PEM.
    with tempfile.NamedTemporaryFile("wb", suffix=".pem", delete=False) as fh:
        fh.write(cert_pem + key_pem)
        combined = fh.name
    ctx = ssl.create_default_context()
    ctx.load_cert_chain(certfile=combined)
    return ctx


def push_empty(push_tokens: list[str]) -> int:
    """Send an empty push to each token. Returns the count successfully sent.

    No-op (returns 0) when certs are absent.
    """
    tokens = [t for t in push_tokens if t]
    if not tokens:
        return 0
    ctx = _client_ssl_context()
    if ctx is None:
        logger.info("APNs not configured; skipping push to %d device(s)", len(tokens))
        return 0

    base = _SANDBOX if apns_use_sandbox() else _PROD
    headers = {
        "apns-topic": pass_type_id(),
        "apns-push-type": "background",
        # Store-and-retry for up to an hour instead of drop-on-first-attempt.
        "apns-expiration": str(int(time.time()) + _APNS_EXPIRATION_WINDOW),
    }
    sent = 0
    try:
        with httpx.Client(http2=True, verify=ctx, timeout=15) as client:
            for token in tokens:
                resp = client.post(f"{base}/3/device/{token}", content=b"{}", headers=headers)
                if resp.status_code == 200:
                    sent += 1
                else:  # pragma: no cover - network dependent
                    logger.warning("APNs push failed (%s): %s", resp.status_code, resp.text)
    except Exception:  # pragma: no cover - network dependent
        logger.exception("APNs push error")
    return sent
