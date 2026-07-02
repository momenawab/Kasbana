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
