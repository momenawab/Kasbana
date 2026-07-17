from rest_framework import serializers

from .utils import normalize_phone


class SendOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)

    def validate_phone(self, value):
        return normalize_phone(value)


class VerifyOTPSerializer(SendOTPSerializer):
    otp = serializers.RegexField(r"^\d{6}$")
