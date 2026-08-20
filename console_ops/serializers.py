from __future__ import annotations

from rest_framework import serializers

from .models import OpsConfiguration


class OpsSettingsSerializer(serializers.ModelSerializer):
    telegram_bot_token = serializers.CharField(write_only=True, required=False, allow_blank=False)
    telegram_configured = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = OpsConfiguration
        fields = [
            "notifications_enabled",
            "hourly_reports_enabled",
            "critical_alerts_enabled",
            "warning_alerts_enabled",
            "deployment_alerts_enabled",
            "backup_alerts_enabled",
            "ssl_alerts_enabled",
            "telegram_chat_id",
            "telegram_bot_token",
            "telegram_configured",
            "quiet_hours_start",
            "quiet_hours_end",
            "thresholds",
        ]

    def get_telegram_configured(self, obj: OpsConfiguration) -> bool:
        return bool(obj.telegram_bot_token_encrypted)

    def validate_thresholds(self, value: dict) -> dict:
        defaults = OpsConfiguration.defaults()
        merged = {**defaults, **value}
        for key, number in merged.items():
            if not isinstance(number, (int, float)) or number < 0:
                raise serializers.ValidationError({key: "Must be a non-negative number."})
        for resource in ("cpu", "ram", "disk"):
            if merged[f"{resource}_warning"] >= merged[f"{resource}_critical"]:
                raise serializers.ValidationError(
                    {resource: "Warning must be lower than critical."}
                )
            if merged[f"{resource}_critical"] > 100:
                raise serializers.ValidationError({resource: "Percent cannot exceed 100."})
        return merged
