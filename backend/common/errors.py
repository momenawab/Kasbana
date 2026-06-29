"""Error envelope, error codes and domain exceptions (contract §3.7).

Every error response is rendered as::

    { "error": { "code": "...", "message": "...", "fields": { ... } } }

Domain exceptions raised by ``core/ledger.py`` (and later billing) map to the
frozen ``ErrorCode`` values below. New codes require a contract PR.
"""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class ErrorCode:
    VALIDATION_ERROR = "VALIDATION_ERROR"  # 400
    UNAUTHENTICATED = "UNAUTHENTICATED"  # 401
    PERMISSION_DENIED = "PERMISSION_DENIED"  # 403
    NOT_FOUND = "NOT_FOUND"  # 404
    CONFLICT = "CONFLICT"  # 409
    ALREADY_ENROLLED = "ALREADY_ENROLLED"  # 409
    TOKEN_EXPIRED = "TOKEN_EXPIRED"  # 410
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"  # 429
    RATE_LIMITED = "RATE_LIMITED"  # 429
    REWARD_NOT_READY = "REWARD_NOT_READY"  # 422
    PLAN_LIMIT = "PLAN_LIMIT"  # 402 (billing, Phase 1.4)
    WALLET_PROVISION_FAILED = "WALLET_PROVISION_FAILED"  # 502
    SERVER_ERROR = "SERVER_ERROR"  # 500


# ── Domain exceptions ─────────────────────────────────────────────────────────
class DomainError(APIException):
    """Base for Kasbana domain exceptions carrying a contract ErrorCode."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = ErrorCode.VALIDATION_ERROR
    default_detail: str = "Request could not be processed."

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.default_detail)


class Conflict(DomainError):
    status_code = status.HTTP_409_CONFLICT
    error_code = ErrorCode.CONFLICT
    default_detail = "Conflicting state."


class AlreadyEnrolled(DomainError):
    status_code = status.HTTP_409_CONFLICT
    error_code = ErrorCode.ALREADY_ENROLLED
    default_detail = "This phone is already enrolled in this program."


class TokenExpired(DomainError):
    status_code = status.HTTP_410_GONE
    error_code = ErrorCode.TOKEN_EXPIRED
    default_detail = "This enrollment token has expired."


class CooldownActive(DomainError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = ErrorCode.COOLDOWN_ACTIVE
    default_detail = "Too soon since the last stamp on this card."


class RateLimited(DomainError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = ErrorCode.RATE_LIMITED
    default_detail = "Stamp rate limit exceeded."


class RewardNotReady(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = ErrorCode.REWARD_NOT_READY
    default_detail = "This card has not reached the reward threshold yet."


class PlanLimit(DomainError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    error_code = ErrorCode.PLAN_LIMIT
    default_detail = "Your plan does not allow this action."


class WalletProvisionFailed(DomainError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = ErrorCode.WALLET_PROVISION_FAILED
    default_detail = "Wallet provisioning failed."


class PayloadTooLarge(DomainError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    error_code = ErrorCode.VALIDATION_ERROR
    default_detail = "File too large."


class UnprocessableEntity(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = ErrorCode.VALIDATION_ERROR
    default_detail = "Request could not be processed."


# Map DRF's built-in status codes to contract error codes.
_STATUS_TO_CODE = {
    status.HTTP_400_BAD_REQUEST: ErrorCode.VALIDATION_ERROR,
    status.HTTP_401_UNAUTHORIZED: ErrorCode.UNAUTHENTICATED,
    status.HTTP_403_FORBIDDEN: ErrorCode.PERMISSION_DENIED,
    status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
    status.HTTP_405_METHOD_NOT_ALLOWED: ErrorCode.VALIDATION_ERROR,
    status.HTTP_406_NOT_ACCEPTABLE: ErrorCode.VALIDATION_ERROR,
    status.HTTP_409_CONFLICT: ErrorCode.CONFLICT,
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: ErrorCode.VALIDATION_ERROR,
    status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.RATE_LIMITED,
}


def _build_envelope(code: str, message: str, fields: Any | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if fields:
        body["fields"] = fields
    return {"error": body}


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF exception handler that wraps every error in the contract envelope."""
    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled exception -> 500. DRF re-raises in DEBUG; in prod we shape it.
        return None

    # Resolve the error code.
    if isinstance(exc, DomainError):
        code = exc.error_code
    elif isinstance(exc, DRFValidationError):
        code = ErrorCode.VALIDATION_ERROR
    else:
        code = _STATUS_TO_CODE.get(response.status_code, ErrorCode.SERVER_ERROR)

    data = response.data
    fields: Any | None = None
    message: str

    if isinstance(exc, DRFValidationError):
        # Field-level errors -> fields map; a top-level message stays generic.
        if isinstance(data, dict):
            fields = data
            message = "Validation failed."
        else:
            message = "Validation failed."
            fields = {"non_field_errors": data}
    elif isinstance(data, dict) and "detail" in data:
        message = str(data["detail"])
    else:
        message = str(data)

    response.data = _build_envelope(code, message, fields)
    return response
