"""Platform Operations, Health & Config endpoints (Phase 14).

Health and all list/detail reads are open to any active admin (the console's
read-open convention). Every *mutation* — toggling a flag/setting, flipping
maintenance mode, retrying a job, replaying a webhook, re-provisioning a pass —
is gated to ``OPS_MANAGE`` (Engineering + super-admin) and audited.
"""

from __future__ import annotations

from ast import literal_eval as _parse_literal  # safe: parses Python literals only

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_celery_results.models import TaskResult
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from billing import webhook_log
from billing.models import WebhookDelivery
from console import audit, ops_health
from console.flags import MAINTENANCE_KEY, maintenance_state, refresh_maintenance_cache
from console.models import AdminUser, FeatureFlag, FeatureFlagOverride, PlatformSetting
from console.permissions import AdminAPIView, IsAdminUser, require
from console.rbac import Permission
from console.serializers_ops import (
    FeatureFlagSerializer,
    MaintenanceSerializer,
    OverrideInputSerializer,
    PlatformSettingSerializer,
    TaskResultSerializer,
    WalletSyncFailureSerializer,
    WebhookDeliverySerializer,
)
from core.models import Merchant
from wallets.models import WalletSyncFailure

_LIST_CAP = 100  # ops monitors show recent rows, not the whole table


def _actor_email(request: Request) -> str:
    actor = request.user if isinstance(request.user, AdminUser) else None
    return getattr(actor, "email", "")


def _ops_write_permissions(view: AdminAPIView) -> list:
    """Reads open to any admin; the mutating method needs OPS_MANAGE."""
    if view.request.method in ("GET", "HEAD", "OPTIONS"):
        return [IsAdminUser()]
    return [IsAdminUser(), require(Permission.OPS_MANAGE)()]


# ── Health ───────────────────────────────────────────────────────────────────
class HealthView(AdminAPIView):
    """GET /ops/health — real API/DB/cache/Celery/queue probes (any admin)."""

    @extend_schema(responses={200: dict})
    def get(self, request: Request) -> Response:
        return Response(ops_health.health_report())


# ── Feature flags ──────────────────────────────────────────────────────────────
class FeatureFlagListView(AdminAPIView):
    """GET /ops/flags — list. POST — create a flag (OPS_MANAGE)."""

    def get_permissions(self):  # type: ignore[no-untyped-def]
        return _ops_write_permissions(self)

    @extend_schema(responses=FeatureFlagSerializer(many=True))
    def get(self, request: Request) -> Response:
        flags = FeatureFlag.objects.prefetch_related("overrides__merchant").all()
        return Response(FeatureFlagSerializer(flags, many=True).data)

    @extend_schema(request=FeatureFlagSerializer, responses=FeatureFlagSerializer)
    def post(self, request: Request) -> Response:
        body = FeatureFlagSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        key = body.validated_data["key"]
        if FeatureFlag.objects.filter(key=key).exists():
            return Response(
                {"error": {"code": "CONFLICT", "message": "A flag with this key exists."}},
                status=409,
            )
        flag = body.save(updated_by_email=_actor_email(request))
        audit.record(
            request,
            "ops.flag_create",
            target_type="feature_flag",
            target_id=key,
            metadata={"enabled": flag.enabled},
        )
        return Response(FeatureFlagSerializer(flag).data, status=201)


class FeatureFlagDetailView(AdminAPIView):
    """PATCH /ops/flags/{key} — edit label/description/enabled (OPS_MANAGE)."""

    def get_permissions(self):  # type: ignore[no-untyped-def]
        return _ops_write_permissions(self)

    @extend_schema(request=FeatureFlagSerializer, responses=FeatureFlagSerializer)
    def patch(self, request: Request, key: str) -> Response:
        flag = get_object_or_404(FeatureFlag, key=key)
        before = flag.enabled
        body = FeatureFlagSerializer(flag, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        body.save(updated_by_email=_actor_email(request))
        audit.record(
            request,
            "ops.flag_update",
            target_type="feature_flag",
            target_id=key,
            metadata={"before": {"enabled": before}, "after": {"enabled": flag.enabled}},
        )
        return Response(FeatureFlagSerializer(flag).data)


class FeatureFlagOverrideView(AdminAPIView):
    """POST /ops/flags/{key}/override — set a per-merchant override.
    DELETE — clear it. Both OPS_MANAGE."""

    permission_classes = [IsAdminUser, require(Permission.OPS_MANAGE)]

    @extend_schema(request=OverrideInputSerializer, responses=FeatureFlagSerializer)
    def post(self, request: Request, key: str) -> Response:
        flag = get_object_or_404(FeatureFlag, key=key)
        body = OverrideInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        merchant = get_object_or_404(Merchant, pk=body.validated_data["merchant_id"])
        FeatureFlagOverride.objects.update_or_create(
            flag=flag, merchant=merchant, defaults={"enabled": body.validated_data["enabled"]}
        )
        audit.record(
            request,
            "ops.flag_override",
            target_type="feature_flag",
            target_id=key,
            metadata={"merchant_id": str(merchant.id), "enabled": body.validated_data["enabled"]},
        )
        flag.refresh_from_db()
        return Response(FeatureFlagSerializer(flag).data)

    @extend_schema(request=OverrideInputSerializer, responses=FeatureFlagSerializer)
    def delete(self, request: Request, key: str) -> Response:
        flag = get_object_or_404(FeatureFlag, key=key)
        merchant_id = str(request.data.get("merchant_id") or "")
        FeatureFlagOverride.objects.filter(flag=flag, merchant_id=merchant_id).delete()
        audit.record(
            request,
            "ops.flag_override_clear",
            target_type="feature_flag",
            target_id=key,
            metadata={"merchant_id": str(merchant_id)},
        )
        flag.refresh_from_db()
        return Response(FeatureFlagSerializer(flag).data)


# ── Platform settings ────────────────────────────────────────────────────────
class PlatformSettingListView(AdminAPIView):
    """GET /ops/settings — all settings (any admin)."""

    @extend_schema(responses=PlatformSettingSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(PlatformSettingSerializer(PlatformSetting.objects.all(), many=True).data)


class PlatformSettingDetailView(AdminAPIView):
    """PATCH /ops/settings/{key} — upsert a setting's value (OPS_MANAGE)."""

    permission_classes = [IsAdminUser, require(Permission.OPS_MANAGE)]

    @extend_schema(request=PlatformSettingSerializer, responses=PlatformSettingSerializer)
    def patch(self, request: Request, key: str) -> Response:
        setting, _ = PlatformSetting.objects.get_or_create(key=key)
        before = setting.value
        setting.value = request.data.get("value", setting.value)
        if "description" in request.data:
            setting.description = request.data["description"]
        setting.updated_by_email = _actor_email(request)
        setting.save()
        audit.record(
            request,
            "ops.setting_update",
            target_type="platform_setting",
            target_id=key,
            metadata={"before": before, "after": setting.value},
        )
        return Response(PlatformSettingSerializer(setting).data)


class MaintenanceView(AdminAPIView):
    """GET /ops/maintenance — current state (any admin).
    PATCH — flip it (OPS_MANAGE); refreshes the enforcement cache immediately."""

    def get_permissions(self):  # type: ignore[no-untyped-def]
        return _ops_write_permissions(self)

    @extend_schema(responses=MaintenanceSerializer)
    def get(self, request: Request) -> Response:
        return Response(maintenance_state(use_cache=False))

    @extend_schema(request=MaintenanceSerializer, responses=MaintenanceSerializer)
    def patch(self, request: Request) -> Response:
        body = MaintenanceSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        value = {
            "enabled": body.validated_data["enabled"],
            "message": body.validated_data.get("message", ""),
        }
        setting, _ = PlatformSetting.objects.get_or_create(key=MAINTENANCE_KEY)
        before = setting.value
        setting.value = value
        setting.updated_by_email = _actor_email(request)
        setting.save()
        state = refresh_maintenance_cache()
        audit.record(
            request,
            "ops.maintenance",
            target_type="platform_setting",
            target_id=MAINTENANCE_KEY,
            metadata={"before": before, "after": value},
        )
        return Response(state)


# ── Task monitor ───────────────────────────────────────────────────────────────
class TaskResultListView(AdminAPIView):
    """GET /ops/tasks — recent Celery task results, filter by ?status= (any admin)."""

    @extend_schema(
        parameters=[OpenApiParameter("status", str, description="e.g. FAILURE / SUCCESS")],
        responses=TaskResultSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        qs = TaskResult.objects.all().order_by("-date_created")
        status = request.query_params.get("status")
        if status:
            qs = qs.filter(status=status.upper())
        return Response(TaskResultSerializer(qs[:_LIST_CAP], many=True).data)


class TaskRetryView(AdminAPIView):
    """POST /ops/tasks/{task_id}/retry — re-enqueue a task by name+args (OPS_MANAGE)."""

    permission_classes = [IsAdminUser, require(Permission.OPS_MANAGE)]

    @extend_schema(request=None, responses={200: dict})
    def post(self, request: Request, task_id: str) -> Response:
        result = get_object_or_404(TaskResult, task_id=task_id)
        # django_celery_results stores args/kwargs as a Python-literal repr string.
        try:
            args = _parse_literal(result.task_args) if result.task_args else ()
            kwargs = _parse_literal(result.task_kwargs) if result.task_kwargs else {}
        except (ValueError, SyntaxError):
            return Response(
                {
                    "error": {
                        "code": "UNPARSEABLE_ARGS",
                        "message": "Can't auto-retry: stored args are not parseable.",
                    }
                },
                status=409,
            )
        from config.celery import app

        async_result = app.send_task(result.task_name, args=list(args), kwargs=dict(kwargs))
        audit.record(
            request,
            "ops.task_retry",
            target_type="task",
            target_id=task_id,
            metadata={"task_name": result.task_name, "new_task_id": async_result.id},
        )
        return Response({"retried": True, "new_task_id": async_result.id})


# ── Webhook deliveries ───────────────────────────────────────────────────────
class WebhookDeliveryListView(AdminAPIView):
    """GET /ops/webhooks — recent deliveries, filter ?provider=/?status= (any admin)."""

    @extend_schema(
        parameters=[OpenApiParameter("provider", str), OpenApiParameter("status", str)],
        responses=WebhookDeliverySerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        qs = WebhookDelivery.objects.all()
        if provider := request.query_params.get("provider"):
            qs = qs.filter(provider=provider)
        if status := request.query_params.get("status"):
            qs = qs.filter(status=status)
        return Response(WebhookDeliverySerializer(qs[:_LIST_CAP], many=True).data)


class WebhookReplayView(AdminAPIView):
    """POST /ops/webhooks/{id}/replay — re-apply a stored delivery (OPS_MANAGE)."""

    permission_classes = [IsAdminUser, require(Permission.OPS_MANAGE)]

    @extend_schema(request=None, responses={200: dict})
    def post(self, request: Request, delivery_id: str) -> Response:
        delivery = get_object_or_404(WebhookDelivery, pk=delivery_id)
        if not delivery.payload:
            return Response(
                {
                    "error": {
                        "code": "NOT_REPLAYABLE",
                        "message": "This delivery has no replayable payload.",
                    }
                },
                status=409,
            )
        from billing import services

        event = webhook_log.event_from_payload(delivery.payload)
        sub = services.apply_webhook_event(event)
        delivery.status = (
            WebhookDelivery.Status.PROCESSED if sub else WebhookDelivery.Status.NO_MERCHANT
        )
        delivery.processed_at = timezone.now()
        delivery.save(update_fields=["status", "processed_at"])
        audit.record(
            request,
            "ops.webhook_replay",
            target_type="webhook_delivery",
            target_id=str(delivery.id),
            metadata={"provider": delivery.provider, "status": delivery.status},
        )
        return Response({"replayed": True, "status": delivery.status})


# ── Wallet sync failures ─────────────────────────────────────────────────────
class WalletFailureListView(AdminAPIView):
    """GET /ops/wallet-failures — recent failures, ?resolved=true/false (any admin)."""

    @extend_schema(
        parameters=[OpenApiParameter("resolved", bool)],
        responses=WalletSyncFailureSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        qs = WalletSyncFailure.objects.all()
        resolved = request.query_params.get("resolved")
        if resolved is not None:
            qs = qs.filter(resolved=resolved.lower() == "true")
        return Response(WalletSyncFailureSerializer(qs[:_LIST_CAP], many=True).data)


class WalletReprovisionView(AdminAPIView):
    """POST /ops/wallet-failures/{id}/reprovision — re-enqueue the wallet task
    and mark the failure resolved (OPS_MANAGE)."""

    permission_classes = [IsAdminUser, require(Permission.OPS_MANAGE)]

    @extend_schema(request=None, responses={200: dict})
    def post(self, request: Request, failure_id: str) -> Response:
        failure = get_object_or_404(WalletSyncFailure, pk=failure_id)
        if failure.customer_card_id is None:
            return Response(
                {"error": {"code": "CARD_GONE", "message": "The customer card no longer exists."}},
                status=409,
            )
        from wallets.tasks import provision_pass, push_pass_update

        task = push_pass_update if failure.operation == "push_update" else provision_pass
        task.delay(str(failure.customer_card_id))
        failure.resolved = True
        failure.resolved_at = timezone.now()
        failure.save(update_fields=["resolved", "resolved_at"])
        audit.record(
            request,
            "ops.wallet_reprovision",
            target_type="wallet_sync_failure",
            target_id=str(failure.id),
            metadata={
                "operation": failure.operation,
                "customer_card_id": str(failure.customer_card_id),
            },
        )
        return Response({"reprovisioned": True})
