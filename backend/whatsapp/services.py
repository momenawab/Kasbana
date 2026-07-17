from __future__ import annotations

import hmac
import secrets
import time

from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken

from .client import WhatsAppClient
from .exceptions import OTPInvalid, OTPRateLimited
from .models import WhatsAppIdentity, WhatsAppMessageLog
from .utils import mask_phone, normalize_phone, otp_digest, phone_key

OTP_TTL = 300  # seconds a code stays valid
COOLDOWN_TTL = 60  # seconds between requests for one number
HOURLY_LIMIT = 5  # codes per number per hour
MAX_ATTEMPTS = 3  # wrong guesses before the code is burned


class OTPService:
    """Send and verify WhatsApp verification codes. Transport is delegated to
    ``WhatsAppClient``; this owns the rate limits, the digest comparison, and
    the account lookup."""

    def __init__(self, client: WhatsAppClient | None = None):
        self.client = client or WhatsAppClient()

    def _key(self, prefix: str, phone: str) -> str:
        return f"wa_otp:{prefix}:{phone_key(phone)}"

    def generate_otp(self, phone: str) -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    def _check_limits(self, phone: str) -> None:
        if cache.get(self._key("cooldown", phone)):
            raise OTPRateLimited("Please wait before requesting another code.")
        # Same key the send path increments — a per-number hourly ceiling. The
        # missing phone argument here was the bug that crashed every send.
        hourly = self._key("hour", phone)
        cache.add(hourly, 0, 3600)
        if int(cache.get(hourly) or 0) >= HOURLY_LIMIT:
            raise OTPRateLimited("Maximum verification messages reached for this hour.")

    def send_otp(self, phone: str) -> None:
        phone = normalize_phone(phone)
        self._check_limits(phone)
        otp = self.generate_otp(phone)

        result = self.client.send_template(phone, "stampn_login", "en", [otp])
        message_id = (result.get("messages") or [{}])[0].get("id", "")
        WhatsAppMessageLog.objects.create(
            message_id=message_id, phone_masked=mask_phone(phone), meta_response=result
        )

        # Expiry is a wall-clock deadline, not a monotonic delta: a code is set by
        # one worker process and verified by another, and monotonic clocks are
        # per-process — comparing them across requests is meaningless. The cache
        # TTL enforces expiry too; this deadline just lets a failed attempt
        # re-store the record without extending its life.
        cache.set(
            self._key("code", phone),
            {"digest": otp_digest(phone, otp), "attempts": 0, "expires_at": time.time() + OTP_TTL},
            OTP_TTL,
        )
        cache.set(self._key("cooldown", phone), True, COOLDOWN_TTL)
        cache.incr(self._key("hour", phone))

    def verify_otp(self, phone: str, otp: str) -> dict[str, str]:
        phone = normalize_phone(phone)
        key = self._key("code", phone)
        record = cache.get(key)
        if not record:
            raise OTPInvalid()

        remaining = int(record.get("expires_at", 0) - time.time())
        if remaining <= 0:
            cache.delete(key)
            raise OTPInvalid()
        if int(record.get("attempts", 0)) >= MAX_ATTEMPTS:
            cache.delete(key)
            raise OTPRateLimited("Too many invalid code attempts.")

        if not hmac.compare_digest(record["digest"], otp_digest(phone, otp)):
            record["attempts"] += 1
            cache.set(key, record, remaining)
            raise OTPInvalid()

        cache.delete(key)  # a code is single-use, burned on success

        # An OTP proves control of a phone; it does not identify an account. Only
        # a previously linked, active user gets tokens — an unknown number can
        # neither create an account nor take one over.
        identity = WhatsAppIdentity.objects.select_related("user").filter(phone=phone).first()
        if not identity or not identity.user.is_active:
            raise OTPInvalid("No active account is linked to this phone.")

        refresh = RefreshToken.for_user(identity.user)
        return {"access": str(refresh.access_token), "refresh": str(refresh)}


def link_phone(user, phone: str) -> WhatsAppIdentity:
    """Associate a verified phone with a Django user. Called from the future
    signup / profile verification flow — the only place a mapping is created."""
    phone = normalize_phone(phone)
    identity, _ = WhatsAppIdentity.objects.update_or_create(user=user, defaults={"phone": phone})
    return identity
