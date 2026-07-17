from __future__ import annotations

import hashlib
import hmac
import re

from django.conf import settings
from rest_framework.exceptions import ValidationError

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone(value: str) -> str:
    phone = value.strip().replace(" ", "").replace("-", "")
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if not _E164.fullmatch(phone):
        raise ValidationError({"phone": "Use an E.164 number, e.g. +2010XXXXXXX."})
    return phone


def phone_key(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()


def otp_digest(phone: str, otp: str) -> str:
    # SECRET_KEY is typed str | None (env helper); it always has a value.
    secret = (settings.SECRET_KEY or "").encode()
    return hmac.new(secret, f"{phone}:{otp}".encode(), hashlib.sha256).hexdigest()


def mask_phone(phone: str) -> str:
    return f"{phone[:3]}••••{phone[-3:]}" if len(phone) > 6 else "••••"
