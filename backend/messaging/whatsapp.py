"""WhatsApp Business API client (Phase 1.7).

A thin wrapper over the Cloud API ``/{phone_id}/messages`` endpoint. When
``WHATSAPP_API_TOKEN`` / ``WHATSAPP_PHONE_ID`` are unset (local/CI) the client
runs in stub mode: it logs and returns a fake message id without any network
call, so the send pipeline is exercisable end-to-end without real credentials.
Real delivery is verified on staging.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.facebook.com/v19.0"


@dataclass(frozen=True)
class SendResult:
    ok: bool
    message_id: str
    stubbed: bool = False


def _config() -> dict[str, str]:
    return getattr(settings, "MESSAGING", {}).get("WHATSAPP", {})


class WhatsAppClient:
    """Send a text message to an E.164 phone number via the WhatsApp Cloud API."""

    def __init__(self) -> None:
        cfg = _config()
        self.token = cfg.get("API_TOKEN", "")
        self.phone_id = cfg.get("PHONE_ID", "")

    @property
    def configured(self) -> bool:
        return bool(self.token and self.phone_id)

    def send_text(self, *, to: str, text: str) -> SendResult:
        if not self.configured:
            logger.info("WhatsApp stub send to %s: %s", to, text[:64])
            return SendResult(ok=True, message_id=f"stub-{to}", stubbed=True)

        resp = httpx.post(
            f"{_GRAPH_BASE}/{self.phone_id}/messages",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text},
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
        message_id = data.get("messages", [{}])[0].get("id", "")
        return SendResult(ok=True, message_id=message_id)
