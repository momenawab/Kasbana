"""Telegram delivery; token decryption is intentionally owned by this module."""

from __future__ import annotations

import httpx
from cryptography.fernet import Fernet
from django.conf import settings

from .models import OpsConfiguration


def _token(config: OpsConfiguration) -> str:
    if not config.telegram_bot_token_encrypted:
        return ""
    return (
        Fernet((settings.OPS_SETTINGS_ENCRYPTION_KEY or "").encode())
        .decrypt(bytes(config.telegram_bot_token_encrypted))
        .decode()
    )


def send(config: OpsConfiguration, text: str) -> bool:
    token = _token(config)
    if not (config.notifications_enabled and token and config.telegram_chat_id):
        return False
    response = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": config.telegram_chat_id, "text": text[:4000]},
        timeout=8.0,
    )
    response.raise_for_status()
    return True
