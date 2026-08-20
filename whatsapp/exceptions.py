from common.errors import DomainError, ErrorCode


class WhatsAppProviderError(DomainError):
    status_code = 502
    error_code = ErrorCode.SERVER_ERROR
    default_detail = "Authentication message could not be sent."


class OTPInvalid(DomainError):
    status_code = 400
    error_code = ErrorCode.VALIDATION_ERROR
    default_detail = "The verification code is invalid or expired."


class OTPRateLimited(DomainError):
    status_code = 429
    error_code = ErrorCode.RATE_LIMITED
    default_detail = "Too many verification requests. Please try again later."
