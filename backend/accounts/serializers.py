"""Account-lifecycle serializers (Phase 1.5 · contract Auth/Account/Settings)."""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from accounts.services import settings_for, unique_slug
from billing.services import subscription_for
from core.enums import Role
from core.models import Merchant, StaffUser

User = get_user_model()
logger = logging.getLogger(__name__)


# ── Auth lifecycle ───────────────────────────────────────────────────────────
class SignupSerializer(serializers.Serializer):
    """POST /auth/signup — create merchant + owner, start the trial."""

    business_name = serializers.CharField(max_length=120)
    owner_name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)  # E.164
    password = serializers.CharField(min_length=8, write_only=True)
    consent = serializers.BooleanField()
    # Optional partner referral code (Phase E.1). Blank/unknown = no attribution.
    referral_code = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_consent(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("PDPL consent is required.")
        return value

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> StaffUser:
        email = validated_data["email"]
        user = User(username=email, email=email, first_name=validated_data["owner_name"][:150])
        user.set_password(validated_data["password"])
        user.save()

        merchant = Merchant.objects.create(
            name=validated_data["business_name"],
            slug=unique_slug(validated_data["business_name"]),
        )
        staff = StaffUser.objects.create(merchant=merchant, user=user, role=Role.OWNER)

        s = settings_for(merchant)
        s.contact_email = email
        s.contact_phone = validated_data["phone"]
        s.save(update_fields=["contact_email", "contact_phone", "updated_at"])

        subscription_for(merchant)  # starts the 14-day trial

        # Best-effort partner attribution (Phase E.1) — never block signup on it.
        code = validated_data.get("referral_code", "")
        if code:
            try:
                from partners.services import attribute_signup

                attribute_signup(merchant, code)
            except Exception:  # pragma: no cover - defensive
                logger.exception("partner attribution failed for %s", merchant.id)

        return staff


class ForgotSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(min_length=8, write_only=True)


class InviteAcceptSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=8, write_only=True)


# ── Settings ─────────────────────────────────────────────────────────────────
class ContactSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)


class BusinessSettingsSerializer(serializers.Serializer):
    """PATCH /settings/business — partial update of branding + contact."""

    name = serializers.CharField(max_length=120, required=False)
    legal_name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    logo_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    color_bg = serializers.CharField(max_length=7, required=False, allow_blank=True)
    color_fg = serializers.CharField(max_length=7, required=False, allow_blank=True)
    contact = ContactSerializer(required=False)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    # Pass-back contact + social links (each optional — shown on the wallet pass
    # back only when filled in).
    facebook_url = serializers.URLField(required=False, allow_blank=True)
    instagram_url = serializers.URLField(required=False, allow_blank=True)
    tiktok_url = serializers.URLField(required=False, allow_blank=True)
    whatsapp = serializers.CharField(max_length=32, required=False, allow_blank=True)
    terms_url = serializers.URLField(required=False, allow_blank=True)
    branches = serializers.CharField(required=False, allow_blank=True)
    # Branded enrollment copy (custom_branding plans only — enforced in the view).
    enroll_headline = serializers.CharField(max_length=80, required=False, allow_blank=True)
    enroll_tagline = serializers.CharField(max_length=160, required=False, allow_blank=True)


class NotificationsSerializer(serializers.Serializer):
    email = serializers.BooleanField(required=False)
    whatsapp = serializers.BooleanField(required=False)


class AccountSettingsSerializer(serializers.Serializer):
    """GET/PATCH /settings/account — language + notification prefs."""

    language = serializers.ChoiceField(choices=["ar", "en"], required=False)
    notifications = NotificationsSerializer(required=False)


class PasswordChangeSerializer(serializers.Serializer):
    current = serializers.CharField(write_only=True)
    new = serializers.CharField(min_length=8, write_only=True)


# ── Response shapes (for OpenAPI fidelity; runtime returns plain dicts) ───────
class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class OkSerializer(serializers.Serializer):
    ok = serializers.BooleanField()


class PasswordChangeOutSerializer(serializers.Serializer):
    """A changed password re-issues the caller's tokens (all sessions revoked)."""

    ok = serializers.BooleanField()
    access = serializers.CharField()
    refresh = serializers.CharField()


class MerchantOutSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    legal_name = serializers.CharField(allow_blank=True)
    slug = serializers.CharField()
    status = serializers.ChoiceField(choices=["trial", "active", "suspended"])
    plan = serializers.ChoiceField(choices=["trial", "starter", "growth", "chain"])
    trial_ends_at = serializers.DateTimeField(allow_null=True)
    logo_url = serializers.URLField(allow_null=True)
    address = serializers.CharField(allow_blank=True)
    color_bg = serializers.CharField(allow_blank=True)
    color_fg = serializers.CharField(allow_blank=True)
    enroll_headline = serializers.CharField(allow_blank=True)
    enroll_tagline = serializers.CharField(allow_blank=True)
    phone = serializers.CharField(allow_blank=True)
    facebook_url = serializers.CharField(allow_blank=True)
    instagram_url = serializers.CharField(allow_blank=True)
    tiktok_url = serializers.CharField(allow_blank=True)
    whatsapp = serializers.CharField(allow_blank=True)
    terms_url = serializers.CharField(allow_blank=True)
    branches = serializers.CharField(allow_blank=True)


class EntitlementsOutSerializer(serializers.Serializer):
    plan = serializers.CharField()
    limits = serializers.DictField()
    features = serializers.DictField()
    usage = serializers.DictField()


class MeOutSerializer(serializers.Serializer):
    merchant = MerchantOutSerializer()
    entitlements = EntitlementsOutSerializer()
    staff = serializers.DictField()
    # Present only on an impersonated session (Phase 6): {admin_email, expires_at}.
    impersonation = serializers.DictField(required=False)


class AccountSettingsOutSerializer(serializers.Serializer):
    language = serializers.CharField()
    notifications = serializers.DictField()


class InviteInfoSerializer(serializers.Serializer):
    merchant_name = serializers.CharField()
    role = serializers.ChoiceField(choices=["OWNER", "ADMIN", "SCANNER"])
    email = serializers.EmailField()
