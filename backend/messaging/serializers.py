"""Messaging serializers (contract §3.6 — Campaign, Segment, Automation, message).

snake_case JSON. ``stats`` on a campaign is a nested ``{delivered, opened}`` block
derived from the model's counters.
"""

from __future__ import annotations

from rest_framework import serializers

from messaging.enums import AutomationKey, MessageChannel
from messaging.models import Automation, Campaign


class CampaignStatsSerializer(serializers.Serializer):
    delivered = serializers.IntegerField()
    opened = serializers.IntegerField()


class CampaignSerializer(serializers.ModelSerializer):
    stats = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            "id",
            "channel",
            "audience",
            "message",
            "status",
            "schedule_at",
            "sent_at",
            "stats",
        ]
        read_only_fields = ["id", "status", "sent_at", "stats"]

    def get_stats(self, obj: Campaign) -> dict[str, int]:
        return {"delivered": obj.delivered, "opened": obj.opened}


class CampaignWriteSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=MessageChannel.choices)
    audience = serializers.CharField(max_length=64)
    message = serializers.CharField()
    schedule_at = serializers.DateTimeField(required=False, allow_null=True)


class SegmentSerializer(serializers.Serializer):
    key = serializers.CharField()
    # ``label`` shadows ``Field.label`` (str) on the base class — harmless here.
    label = serializers.CharField()  # type: ignore[assignment]
    count = serializers.IntegerField()


class AutomationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Automation
        fields = ["key", "enabled", "channel", "timing", "template"]
        read_only_fields = ["key"]


class AutomationWriteSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(required=False)
    channel = serializers.ChoiceField(choices=MessageChannel.choices, required=False)
    timing = serializers.CharField(required=False, allow_blank=True, max_length=64)
    template = serializers.CharField(required=False, allow_blank=True)


class CustomerMessageSerializer(serializers.Serializer):
    # PUSH = free wallet notification · WHATSAPP = paid/metered · BOTH = each.
    channel = serializers.ChoiceField(choices=MessageChannel.choices)
    text = serializers.CharField()


AUTOMATION_KEYS = [k for k, _ in AutomationKey.choices]
