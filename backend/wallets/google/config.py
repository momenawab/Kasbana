"""Google Wallet configuration + service-account loading (contract §3.8).

Reads ``WALLET["GOOGLE"]`` (issuer id + service-account key path). When the key
is absent (local/dev), ``load_service_account`` returns ``None`` and the backend
degrades to no-op so the rest of the app keeps working.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, cast

from django.conf import settings

_DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"


@dataclass
class ServiceAccount:
    client_email: str
    private_key: str  # PEM
    token_uri: str = _DEFAULT_TOKEN_URI


def _google() -> dict[str, Any]:
    return cast("dict[str, Any]", settings.WALLET["GOOGLE"])


def issuer_id() -> str:
    return _google().get("ISSUER_ID", "")


def sa_key_path() -> str:
    return _google().get("SA_KEY_PATH", "")


def load_service_account() -> ServiceAccount | None:
    """Load the SA email + private key from the JSON key file, or ``None``."""
    path = sa_key_path()
    if not path or not os.path.exists(path):
        return None
    with open(path) as fh:
        data = json.load(fh)
    if "client_email" not in data or "private_key" not in data:
        return None
    return ServiceAccount(
        client_email=data["client_email"],
        private_key=data["private_key"],
        token_uri=data.get("token_uri", _DEFAULT_TOKEN_URI),
    )


def is_configured() -> bool:
    return bool(issuer_id()) and load_service_account() is not None
