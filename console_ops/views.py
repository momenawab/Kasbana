from __future__ import annotations

from cryptography.fernet import Fernet
from django.conf import settings
from rest_framework.request import Request
from rest_framework.response import Response

from console import audit
from console.enums import AdminRole
from console.permissions import AdminAPIView

from .models import OpsAlert, OpsConfiguration
from .serializers import OpsSettingsSerializer
from .services import dashboard
from .telegram import send


class SuperAdminOpsView(AdminAPIView):
    allowed_roles = {AdminRole.SUPER_ADMIN}


class OpsDashboardView(SuperAdminOpsView):
    def get(self, request: Request) -> Response:
        audit.record(request, "stampn_ops.dashboard_read", target_type="ops")
        return Response(dashboard())


class OpsRefreshView(SuperAdminOpsView):
    def post(self, request: Request) -> Response:
        result = dashboard(refresh=True)
        audit.record(request, "stampn_ops.refresh", target_type="ops")
        return Response(result)


class OpsAlertListView(SuperAdminOpsView):
    def get(self, request: Request) -> Response:
        status = request.query_params.get("status", "open")
        rows = OpsAlert.objects.filter(status=status)[:100]
        return Response(
            {
                "results": [
                    {
                        "id": str(x.id),
                        "severity": x.severity,
                        "status": x.status,
                        "title": x.title,
                        "detail": x.detail,
                        "first_seen_at": x.first_seen_at,
                        "last_seen_at": x.last_seen_at,
                        "occurrences": x.occurrences,
                    }
                    for x in rows
                ]
            }
        )


class OpsSettingsView(SuperAdminOpsView):
    def get(self, request: Request) -> Response:
        return Response(OpsSettingsSerializer(OpsConfiguration.current()).data)

    def patch(self, request: Request) -> Response:
        config = OpsConfiguration.current()
        body = OpsSettingsSerializer(config, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        token = body.validated_data.pop("telegram_bot_token", None)
        config = body.save()
        if token:
            config.telegram_bot_token_encrypted = Fernet(
                (settings.OPS_SETTINGS_ENCRYPTION_KEY or "").encode()
            ).encrypt(token.encode())
            config.save(update_fields=["telegram_bot_token_encrypted", "updated_at"])
        audit.record(request, "stampn_ops.settings_update", target_type="ops")
        return Response(OpsSettingsSerializer(config).data)


class TelegramTestView(SuperAdminOpsView):
    def post(self, request: Request) -> Response:
        ok = send(OpsConfiguration.current(), "✅ Stampn Ops test notification")
        audit.record(request, "stampn_ops.telegram_test", target_type="ops", metadata={"sent": ok})
        return Response({"sent": ok})


class WidgetView(SuperAdminOpsView):
    """Authenticated for now; mobile clients will use scoped device tokens later."""

    def get(self, request: Request) -> Response:
        d = dashboard()
        s = d.get("server", {})
        return Response(
            {
                "status": d["status"],
                "healthScore": d["health_score"],
                "cpu": s.get("cpu_percent"),
                "ram": s.get("ram_percent"),
                "disk": s.get("disk_percent"),
                "load": s.get("load_1"),
                "containers": d.get("docker", {}).get("running"),
                "onlineUsers": d.get("business", {}).get("online_users"),
                "responseTime": d.get("api", {}).get("response_time_ms"),
                "version": d.get("version"),
                "lastDeploy": d.get("last_deploy_at"),
            }
        )
