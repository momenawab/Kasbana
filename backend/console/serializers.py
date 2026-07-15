"""Admin API serializers (Phase 1 — auth + me)."""

from __future__ import annotations

from rest_framework import serializers


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class AdminTokenSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class AdminRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class AdminAccessSerializer(serializers.Serializer):
    access = serializers.CharField()


class AdminMeSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    name = serializers.CharField(allow_blank=True)
    role = serializers.CharField()
    mfa_enabled = serializers.BooleanField()
    mfa_required = serializers.BooleanField()
    permissions = serializers.ListField(child=serializers.CharField())


# ── Phase 15: MFA + sessions + step-up ──────────────────────────────────────
class AdminLoginResultSerializer(serializers.Serializer):
    """Login outcome. ``status`` is ``ok`` (tokens present), ``mfa_required``
    (enter a code), or ``mfa_setup`` (enrol first — QR + secret present)."""

    status = serializers.ChoiceField(choices=["ok", "mfa_required", "mfa_setup"])
    access = serializers.CharField(required=False)
    refresh = serializers.CharField(required=False)
    pending_token = serializers.CharField(required=False)
    otpauth_uri = serializers.CharField(required=False)
    secret = serializers.CharField(required=False)
    qr = serializers.CharField(required=False)


class MfaVerifySerializer(serializers.Serializer):
    pending_token = serializers.CharField()
    code = serializers.CharField()


class MfaSetupSerializer(serializers.Serializer):
    """Start MFA enrolment for the already-logged-in admin (voluntary opt-in)."""

    otpauth_uri = serializers.CharField()
    secret = serializers.CharField()
    qr = serializers.CharField()


class MfaConfirmSerializer(serializers.Serializer):
    code = serializers.CharField()


class StepUpSerializer(serializers.Serializer):
    """Re-prove credentials for a sensitive action. Password always; a TOTP code
    too when the admin has MFA enabled."""

    password = serializers.CharField(trim_whitespace=False)
    code = serializers.CharField(required=False, allow_blank=True)


class AdminSessionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    user_agent = serializers.CharField(allow_blank=True)
    ip = serializers.IPAddressField(allow_null=True)
    created_at = serializers.DateTimeField()
    last_seen_at = serializers.DateTimeField(allow_null=True)
    current = serializers.BooleanField()
