"""Serializers for the compliance tools (Phase 13, PDPL)."""

from __future__ import annotations

from rest_framework import serializers

from console.models import RetentionPolicy
from core.models import CustomerCard


class RetentionPolicySerializer(serializers.ModelSerializer):
    """The global data-retention policy. Windows are days; 0 = keep forever."""

    class Meta:
        model = RetentionPolicy
        fields = [
            "inactive_customer_days",
            "closed_merchant_days",
            "audit_log_days",
            "notes",
            "updated_by_email",
            "updated_at",
        ]
        read_only_fields = ["updated_by_email", "updated_at"]

    def validate_inactive_customer_days(self, v: int) -> int:
        return self._non_negative(v)

    def validate_closed_merchant_days(self, v: int) -> int:
        return self._non_negative(v)

    def validate_audit_log_days(self, v: int) -> int:
        return self._non_negative(v)

    @staticmethod
    def _non_negative(v: int) -> int:
        if v < 0:
            raise serializers.ValidationError("Retention window can't be negative (0 = keep).")
        return v


class MerchantDeleteConfirmSerializer(serializers.Serializer):
    """Typed-confirm payload for the irreversible right-to-be-forgotten delete.

    ``confirm`` must exactly match the merchant's slug — the frontend makes the
    operator type it, so a delete can never be a stray click.
    """

    confirm = serializers.CharField()
    reason = serializers.CharField()


class ConsentRecordSerializer(serializers.ModelSerializer):
    """A customer's PDPL consent state (from ``CustomerCard.consent_at``)."""

    class Meta:
        model = CustomerCard
        fields = [
            "id",
            "customer_phone",
            "customer_name",
            "customer_email",
            "status",
            "consent_at",
            "enrolled_at",
        ]
