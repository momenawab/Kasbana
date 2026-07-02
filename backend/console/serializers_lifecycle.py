"""Lifecycle + moderation serializers (Phase 9)."""

from __future__ import annotations

from rest_framework import serializers


class MerchantRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()


class PipelineStageSerializer(serializers.Serializer):
    stage = serializers.CharField()
    count = serializers.IntegerField()
    merchants = MerchantRefSerializer(many=True)


class PipelineSerializer(serializers.Serializer):
    stages = PipelineStageSerializer(many=True)


class AtRiskSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()
    health_score = serializers.IntegerField()
    reasons = serializers.ListField(child=serializers.CharField())


class SuspendSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


# ── moderation ──────────────────────────────────────────────────────────────
class ContentFlagSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    merchant = MerchantRefSerializer()
    target_type = serializers.CharField()
    target_id = serializers.CharField()
    # ``label``/``source`` are also typed attributes on DRF's base Field, so mypy
    # flags the same-named declarations — they're valid field names at runtime.
    label = serializers.CharField()  # type: ignore[assignment]
    reason = serializers.CharField()
    source = serializers.CharField()  # type: ignore[assignment]
    status = serializers.CharField()
    resolution_notes = serializers.CharField()
    created_at = serializers.DateTimeField()
    resolved_at = serializers.DateTimeField(allow_null=True)


class ResolveFlagSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ScanResultSerializer(serializers.Serializer):
    created = serializers.IntegerField()
    scanned_cards = serializers.IntegerField()
    scanned_merchants = serializers.IntegerField()
