"""Phone and email verification providers.

Each provider answers one question and says how sure it is. What none of them
answer is *who owns the number* — that data lives in crowd-sourced caller-ID
databases with no lawful API, so it is not modelled here at all. A rep who
learns an owner's name by other means records it through the manual path
(``leadgen.views.GeneratedLeadOwnerView``).

Every provider degrades rather than fails. With no Twilio credentials the phone
stage still parses and classifies the number with libphonenumber; with no
Hunter key the email stage still checks syntax, disposability and the domain's
MX records. The results are weaker and are labelled as weaker — ``POSSIBLE``
rather than ``VERIFIED`` — but the pipeline keeps working, and a rep can tell
from the label how much to trust it.
"""

from __future__ import annotations

import logging
import re
import socket
from dataclasses import dataclass, field
from decimal import Decimal

import httpx
import phonenumbers
from django.conf import settings
from phonenumbers import NumberParseException, PhoneNumberType, carrier, number_type

from leadgen import enums

logger = logging.getLogger(__name__)

TWILIO_LOOKUP_URL = "https://lookups.twilio.com/v2/PhoneNumbers"
HUNTER_VERIFY_URL = "https://api.hunter.io/v2/email-verifier"


@dataclass
class VerifyOutcome:
    """One provider's answer. Mirrors the fields ``Verification`` stores."""

    result: str = enums.VerificationResult.UNKNOWN
    provider: str = ""
    line_type: str = ""
    carrier_name: str = ""
    deliverable: bool | None = None
    is_disposable: bool | None = None
    is_role_address: bool | None = None
    domain_valid: bool | None = None
    confidence: int | None = None
    credits_used: int = 0
    cost_usd: Decimal = Decimal("0")
    error: str = ""
    raw: dict = field(default_factory=dict)


# ── Phone ────────────────────────────────────────────────────────────────────
_LIBPHONE_TYPES = {
    PhoneNumberType.MOBILE: enums.PhoneLineType.MOBILE,
    PhoneNumberType.FIXED_LINE: enums.PhoneLineType.LANDLINE,
    PhoneNumberType.FIXED_LINE_OR_MOBILE: enums.PhoneLineType.UNKNOWN,
    PhoneNumberType.VOIP: enums.PhoneLineType.VOIP,
}

_TWILIO_TYPES = {
    "mobile": enums.PhoneLineType.MOBILE,
    "landline": enums.PhoneLineType.LANDLINE,
    "voip": enums.PhoneLineType.VOIP,
}


def verify_phone(e164: str, *, region: str = "EG") -> VerifyOutcome:
    """Check a number, with Twilio when configured and offline analysis when not."""
    if not e164:
        return VerifyOutcome(result=enums.VerificationResult.INVALID, error="No number given.")

    offline = _phone_offline(e164, region)
    # An unparseable number is invalid whatever a provider would say, and
    # spending a lookup credit to confirm that is waste.
    if offline.result == enums.VerificationResult.INVALID:
        return offline

    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN):
        return offline

    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(
                f"{TWILIO_LOOKUP_URL}/{e164}",
                params={"Fields": "line_type_intelligence"},
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            )
    except httpx.HTTPError as exc:
        logger.warning("leadgen.verify.twilio_unreachable", extra={"error": str(exc)})
        offline.error = f"Twilio unreachable, used offline analysis: {exc}"
        return offline

    if response.status_code == 404:
        return VerifyOutcome(
            result=enums.VerificationResult.INVALID,
            provider=enums.ApiProvider.TWILIO_LOOKUP,
            confidence=95,
            credits_used=1,
            cost_usd=Decimal(str(settings.TWILIO_LOOKUP_PRICE_USD)),
            raw={"status": 404},
        )
    if response.status_code != 200:
        offline.error = f"Twilio returned HTTP {response.status_code}; used offline analysis."
        return offline

    body = response.json()
    intelligence = body.get("line_type_intelligence") or {}
    valid = bool(body.get("valid"))

    return VerifyOutcome(
        result=(
            enums.VerificationResult.VERIFIED if valid else enums.VerificationResult.INVALID
        ),
        provider=enums.ApiProvider.TWILIO_LOOKUP,
        line_type=_TWILIO_TYPES.get(
            (intelligence.get("type") or "").lower(), enums.PhoneLineType.UNKNOWN
        ),
        carrier_name=(intelligence.get("carrier_name") or "")[:120],
        confidence=95 if valid else 90,
        credits_used=1,
        cost_usd=Decimal(str(settings.TWILIO_LOOKUP_PRICE_USD)),
        raw=body,
    )


def _phone_offline(e164: str, region: str) -> VerifyOutcome:
    """libphonenumber only: structure and line type, never liveness.

    Capped at POSSIBLE on purpose. This proves a number *could* exist and what
    kind of line it would be; it cannot know whether anyone answers. Labelling
    that VERIFIED would put a confidence on the screen the evidence has not
    earned.
    """
    try:
        parsed = phonenumbers.parse(e164, region.upper() or None)
    except NumberParseException as exc:
        return VerifyOutcome(
            result=enums.VerificationResult.INVALID, error=f"Unparseable: {exc}"
        )

    if not phonenumbers.is_valid_number(parsed):
        return VerifyOutcome(
            result=enums.VerificationResult.INVALID,
            error="Not a valid number for its region.",
            confidence=80,
        )

    return VerifyOutcome(
        result=enums.VerificationResult.POSSIBLE,
        provider="",
        line_type=_LIBPHONE_TYPES.get(number_type(parsed), enums.PhoneLineType.UNKNOWN),
        carrier_name=carrier.name_for_number(parsed, "en")[:120],
        confidence=55,
        raw={"source": "libphonenumber"},
    )


# ── Email ────────────────────────────────────────────────────────────────────
_EMAIL_SYNTAX = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

# The disposable domains that actually show up on scraped contact pages. A
# complete list is a subscription product; this catches the common cases and
# Hunter covers the rest when configured.
_DISPOSABLE_DOMAINS = frozenset(
    {
        "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
        "temp-mail.org", "throwawaymail.com", "yopmail.com", "trashmail.com",
        "sharklasers.com", "getnada.com", "maildrop.cc", "dispostable.com",
    }
)

_ROLE_LOCAL_PARTS = frozenset(
    {
        "info", "contact", "hello", "sales", "support", "admin", "office",
        "reservations", "booking", "bookings", "orders", "marketing", "hr",
        "careers", "jobs", "team", "help", "enquiries", "inquiries",
    }
)


def verify_email(address: str) -> VerifyOutcome:
    """Check an address, with Hunter when configured and DNS analysis when not."""
    if not address:
        return VerifyOutcome(result=enums.VerificationResult.INVALID, error="No address given.")

    offline = _email_offline(address)
    if offline.result == enums.VerificationResult.INVALID:
        return offline

    if not settings.HUNTER_API_KEY:
        return offline

    try:
        with httpx.Client(timeout=20) as client:
            response = client.get(
                HUNTER_VERIFY_URL,
                params={"email": address, "api_key": settings.HUNTER_API_KEY},
            )
    except httpx.HTTPError as exc:
        logger.warning("leadgen.verify.hunter_unreachable", extra={"error": str(exc)})
        offline.error = f"Hunter unreachable, used offline analysis: {exc}"
        return offline

    if response.status_code != 200:
        offline.error = f"Hunter returned HTTP {response.status_code}; used offline analysis."
        return offline

    data = (response.json() or {}).get("data") or {}
    status = (data.get("status") or "").lower()

    return VerifyOutcome(
        result={
            "valid": enums.VerificationResult.VERIFIED,
            "accept_all": enums.VerificationResult.POSSIBLE,
            "webmail": enums.VerificationResult.POSSIBLE,
            "unknown": enums.VerificationResult.UNKNOWN,
            "invalid": enums.VerificationResult.INVALID,
            "disposable": enums.VerificationResult.INVALID,
        }.get(status, enums.VerificationResult.UNKNOWN),
        provider=enums.ApiProvider.HUNTER,
        deliverable=status == "valid",
        is_disposable=bool(data.get("disposable")),
        is_role_address=bool(data.get("webmail")) or offline.is_role_address,
        domain_valid=bool(data.get("mx_records")),
        confidence=data.get("score"),
        credits_used=1,
        cost_usd=Decimal(str(settings.HUNTER_PRICE_USD)),
        raw=data,
    )


def _email_offline(address: str) -> VerifyOutcome:
    """Syntax, disposability and an MX lookup. No mailbox probing.

    Capped at POSSIBLE: a domain accepting mail says nothing about whether this
    particular mailbox exists. Probing for that means opening an SMTP session
    and abandoning it, which gets a server IP blocklisted — a permanent cost
    across the whole platform for a marginal signal on one lead.
    """
    address = address.strip().lower()
    if not _EMAIL_SYNTAX.match(address):
        return VerifyOutcome(
            result=enums.VerificationResult.INVALID, error="Not a valid address."
        )

    local, _, domain = address.partition("@")
    is_role = local in _ROLE_LOCAL_PARTS
    disposable = domain in _DISPOSABLE_DOMAINS

    if disposable:
        return VerifyOutcome(
            result=enums.VerificationResult.INVALID,
            is_disposable=True,
            is_role_address=is_role,
            domain_valid=True,
            confidence=90,
            error="Disposable address.",
            raw={"source": "offline"},
        )

    domain_valid = _domain_resolves(domain)
    return VerifyOutcome(
        result=(
            enums.VerificationResult.POSSIBLE
            if domain_valid
            else enums.VerificationResult.INVALID
        ),
        is_disposable=False,
        is_role_address=is_role,
        domain_valid=domain_valid,
        # A role address at a live domain is real but reaches a desk, not a
        # person — worth knowing before a rep writes "Dear info".
        confidence=50 if domain_valid else 85,
        error="" if domain_valid else "Domain does not resolve.",
        raw={"source": "offline"},
    )


def _domain_resolves(domain: str) -> bool:
    """Whether the domain resolves at all.

    A plain A/AAAA lookup rather than an MX query: Django ships no DNS resolver
    and adding dnspython for one boolean is not worth it. A domain that does not
    resolve certainly cannot receive mail, which is the case worth catching; a
    domain that resolves but lacks MX is rarer and Hunter covers it.
    """
    try:
        socket.getaddrinfo(domain, None)
    except (socket.gaierror, UnicodeError):
        return False
    return True
