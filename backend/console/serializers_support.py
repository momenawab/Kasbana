"""Support tools serializers (Phase 6)."""

from __future__ import annotations

from rest_framework import serializers


class ImpersonateRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class ImpersonateResponseSerializer(serializers.Serializer):
    impersonation_id = serializers.UUIDField()
    access = serializers.CharField()
    target_email = serializers.EmailField()
    expires_at = serializers.DateTimeField()


class ImpersonationEndSerializer(serializers.Serializer):
    impersonation_id = serializers.UUIDField()


class ImpersonationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    admin_email = serializers.EmailField()
    target_email = serializers.EmailField()
    reason = serializers.CharField()
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    active = serializers.BooleanField()


class SupportNoteSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    admin_email = serializers.EmailField()
    body = serializers.CharField()
    created_at = serializers.DateTimeField()


class SupportNoteCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=4000)


class ResendInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ReasonOnlySerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class OkSerializer(serializers.Serializer):
    ok = serializers.BooleanField()


class ActivityEventSerializer(serializers.Serializer):
    type = serializers.CharField()
    at = serializers.DateTimeField()
    summary = serializers.CharField()
    meta = serializers.DictField()
