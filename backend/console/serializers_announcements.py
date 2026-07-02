"""Announcement serializers (Phase 10)."""

from __future__ import annotations

from rest_framework import serializers

from console.models import Announcement


class AnnouncementStatsSerializer(serializers.Serializer):
    recipients = serializers.IntegerField()
    delivered = serializers.IntegerField()
    emails_sent = serializers.IntegerField()
    opened = serializers.IntegerField()
    open_rate = serializers.FloatField()


class AnnouncementSerializer(serializers.ModelSerializer):
    stats = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "body",
            "channel",
            "audience",
            "audience_param",
            "status",
            "schedule_at",
            "sent_at",
            "recipients",
            "emails_sent",
            "created_at",
            "updated_at",
            "stats",
        ]
        read_only_fields = ["status", "sent_at", "recipients", "emails_sent"]

    def get_stats(self, obj: Announcement) -> dict:
        from console.announcements import stats

        return stats(obj)


class AnnouncementWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ["title", "body", "channel", "audience", "audience_param", "schedule_at"]


class AudiencePreviewSerializer(serializers.Serializer):
    recipients = serializers.IntegerField()
