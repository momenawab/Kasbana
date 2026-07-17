from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings

from .exceptions import WhatsAppProviderError
from .utils import mask_phone

logger = logging.getLogger(__name__)


class WhatsAppClient:
    """Only Meta Graph API transport; policy and OTP logic stay in services."""

    def __init__(
        self,
        *,
        token: str | None = None,
        phone_number_id: str | None = None,
        transport: httpx.Client | None = None,
    ):
        self.token = token if token is not None else settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = (
            phone_number_id if phone_number_id is not None else settings.WHATSAPP_PHONE_NUMBER_ID
        )
        self.version = settings.WHATSAPP_API_VERSION
        self.http = transport or httpx.Client(timeout=httpx.Timeout(8.0, connect=3.0))

    @property
    def url(self) -> str:
        return f"https://graph.facebook.com/{self.version}/{self.phone_number_id}/messages"

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(3):
            try:
                response = self.http.post(
                    self.url, headers={"Authorization": f"Bearer {self.token}"}, json=payload
                )
                if response.status_code < 500:
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPError as exc:
                if attempt == 2:
                    logger.warning("whatsapp_api_failed error=%s", str(exc)[:160])
                    raise WhatsAppProviderError() from exc
        raise WhatsAppProviderError()

    def send_template(
        self, to: str, template_name: str, language: str, parameters: list[str]
    ) -> dict[str, Any]:
        logger.info("whatsapp_template_send phone=%s template=%s", mask_phone(to), template_name)
        return self._post(
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": language},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [{"type": "text", "text": p} for p in parameters],
                        }
                    ],
                },
            }
        )

    def send_text(self, to: str, message: str) -> dict[str, Any]:
        return self._post(
            {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": message}}
        )

    def mark_as_read(self, message_id: str) -> dict[str, Any]:
        return self._post(
            {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}
        )
