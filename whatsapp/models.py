from __future__ import annotations

from django.conf import settings
from django.db import models


class WhatsAppIdentity(models.Model):
    """Maps a verified phone number to exactly one Django user. An OTP proves
    control of a phone; this row is what turns that into an identity."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="whatsapp_identity"
    )
    phone = models.CharField(max_length=16, unique=True, db_index=True)
    verified_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"whatsapp_identity(user={self.user_id})"


class WhatsAppMessageLog(models.Model):
    """An audit trail of outbound codes and their delivery status. Never stores
    the code or the raw phone — only a masked number and Meta's message id."""

    message_id = models.CharField(max_length=128, unique=True, blank=True)
    phone_masked = models.CharField(max_length=24)
    direction = models.CharField(max_length=12, default="outbound")
    status = models.CharField(max_length=32, default="sent")
    error = models.TextField(blank=True)
    meta_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"whatsapp_log({self.phone_masked} · {self.status})"
