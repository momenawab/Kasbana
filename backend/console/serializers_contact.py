"""Serializers for inbound support/contact messages.

``ContactMessageCreateSerializer`` is what the *public* marketing form posts
(with a honeypot); ``ContactMessageSerializer`` is the admin-facing read shape.
"""

from __future__ import annotations

from rest_framework import serializers

from console.models import ContactMessage


class ContactMessageCreateSerializer(serializers.ModelSerializer):
    """Public write shape. ``botcheck`` is a honeypot — a real person leaves it
    empty; a bot that fills it is rejected quietly by the view."""

    botcheck = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message", "botcheck"]

    def create(self, validated_data):
        validated_data.pop("botcheck", None)
        return super().create(validated_data)


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = [
            "id",
            "name",
            "email",
            "subject",
            "message",
            "status",
            "read_at",
            "replied_at",
            "created_at",
        ]
        read_only_fields = fields


class ContactReplySerializer(serializers.Serializer):
    """Admin reply body — the free-text message emailed back to the customer."""

    message = serializers.CharField(min_length=1, trim_whitespace=True)


class AdminContactMessageCreateSerializer(serializers.ModelSerializer):
    """Admin-created contact message — lets the admin compose a message entry
    with a specific recipient so it can then be replied to via the existing flow."""

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message"]
