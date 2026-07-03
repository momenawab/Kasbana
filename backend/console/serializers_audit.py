"""Serializers for the audit-log viewer (Phase 13)."""

from __future__ import annotations

from rest_framework import serializers

from console.models import AdminAuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """One audit row. ``metadata`` carries before/after + reason for the drawer."""

    class Meta:
        model = AdminAuditLog
        fields = [
            "id",
            "actor_email",
            "action",
            "target_type",
            "target_id",
            "metadata",
            "ip",
            "user_agent",
            "created_at",
        ]
