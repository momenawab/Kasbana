"""Admin-team management serializers (Phase 12)."""

from __future__ import annotations

from rest_framework import serializers

from console.enums import AdminRole
from console.models import AdminUser
from console.rbac import mfa_required, permissions_for


class AdminUserSerializer(serializers.ModelSerializer):
    mfa_required = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = AdminUser
        fields = [
            "id",
            "email",
            "name",
            "role",
            "is_active",
            "mfa_enabled",
            "mfa_required",
            "permissions",
            "last_login_at",
            "created_at",
        ]

    def get_mfa_required(self, admin: AdminUser) -> bool:
        return mfa_required(admin.role)

    def get_permissions(self, admin: AdminUser) -> list[str]:
        return sorted(permissions_for(admin.role))


class AdminInviteSerializer(serializers.Serializer):
    """Create a new admin. A one-time temporary password is generated server-side
    and returned once (MFA + a proper invite-email flow are Phase 15)."""

    email = serializers.EmailField()
    name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=AdminRole.choices)


class AdminUpdateSerializer(serializers.Serializer):
    """Change an admin's role and/or active state. Both optional; ``reason`` is
    always required (role/active changes are security-sensitive and audited)."""

    role = serializers.ChoiceField(choices=AdminRole.choices, required=False)
    is_active = serializers.BooleanField(required=False)
    reason = serializers.CharField(max_length=500)


class AdminInviteResultSerializer(serializers.Serializer):
    admin = AdminUserSerializer()
    temporary_password = serializers.CharField()


class AdminActivitySerializer(serializers.Serializer):
    action = serializers.CharField()
    target_type = serializers.CharField(allow_blank=True)
    target_id = serializers.CharField(allow_blank=True)
    metadata = serializers.DictField()
    created_at = serializers.DateTimeField()
