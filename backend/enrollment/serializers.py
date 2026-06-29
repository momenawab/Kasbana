"""Enrollment serializers (contract §3.6 — snake_case JSON keys)."""

from __future__ import annotations

import re

from rest_framework import serializers

# E.164: optional +, leading non-zero, 7–14 more digits.
_E164 = re.compile(r"^\+?[1-9]\d{7,14}$")


class EnrollLandingSerializer(serializers.Serializer):
    """GET /enroll/{token} response — public program details for the join page."""

    merchant_name = serializers.CharField()
    card_name = serializers.CharField()
    reward_title = serializers.CharField()
    stamps_required = serializers.IntegerField()
    color_bg = serializers.CharField(allow_blank=True)
    color_fg = serializers.CharField(allow_blank=True)
    logo_url = serializers.CharField(allow_blank=True)


class EnrollRequestSerializer(serializers.Serializer):
    """POST /enroll/{token} request body."""

    customer_phone = serializers.CharField(max_length=20)
    customer_name = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default=""
    )
    customer_email = serializers.EmailField(required=False, allow_blank=True, default="")
    birthday = serializers.DateField(required=False, allow_null=True, default=None)
    consent = serializers.BooleanField()

    def validate_customer_phone(self, value: str) -> str:
        normalized = value.strip().replace(" ", "")
        if not _E164.match(normalized):
            raise serializers.ValidationError("Enter a valid phone number in E.164 format.")
        return normalized

    def validate_consent(self, value: bool) -> bool:
        # PDPL: enrollment requires explicit consent.
        if value is not True:
            raise serializers.ValidationError("Consent is required to enroll.")
        return value


class EnrollResponseSerializer(serializers.Serializer):
    """POST /enroll/{token} success response."""

    customer_card_id = serializers.UUIDField()
    stamp_count = serializers.IntegerField()
    stamps_required = serializers.IntegerField()
    apple_pass_url = serializers.CharField(allow_null=True)
    google_save_url = serializers.CharField(allow_null=True)
