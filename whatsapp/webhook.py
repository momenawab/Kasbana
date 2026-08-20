from __future__ import annotations

import hashlib
import hmac
import logging

from django.conf import settings

from .models import WhatsAppMessageLog

logger = logging.getLogger(__name__)


def valid_signature(raw: bytes, signature: str) -> bool:
    # No secret configured → reject every webhook. Fail closed: an unsigned
    # payload must never be trusted just because the app is half-provisioned.
    secret = settings.WHATSAPP_APP_SECRET or ""
    if not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def process(payload: dict) -> None:
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for status in change.get("value", {}).get("statuses", []):
                message_id = status.get("id", "")
                if not message_id:
                    continue
                WhatsAppMessageLog.objects.filter(message_id=message_id).update(
                    status=status.get("status", "unknown"),
                    meta_response=status,
                    error=(status.get("errors") or [{}])[0].get("title", ""),
                )
