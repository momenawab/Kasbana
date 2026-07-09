"""Serializers for inbound "Get started" leads.

``LeadCreateSerializer`` is what the *public* marketing form posts (with a
honeypot); ``LeadSerializer`` is the admin-facing read shape.
"""

from __future__ import annotations

from rest_framework import serializers

from console.models import Lead


class LeadCreateSerializer(serializers.ModelSerializer):
    """Public write shape. ``botcheck`` is a honeypot — a real person leaves it
    empty; a bot that fills it is rejected quietly by the view."""

    botcheck = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Lead
        fields = ["name", "email", "phone", "business_name", "botcheck"]

    def create(self, validated_data):
        validated_data.pop("botcheck", None)
        return super().create(validated_data)


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "business_name",
            "status",
            "contacted_at",
            "created_at",
        ]
        read_only_fields = fields
