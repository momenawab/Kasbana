"""Subscription management endpoints (Phase 4).

Operate any merchant's subscription: change plan/status directly, extend a
trial, toggle comp (free access), lock/unlock, and view the change history.
All mutations require a ``reason`` (except extend-trial, where it's optional
per the plan doc) and are gated to Super-admin/Finance; reads are open to any
admin, matching the Merchant directory (Phase 2) and Plan catalogue (Phase 3).
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from billing import entitlements, services
from billing.plans import LIMIT_CAPABILITIES, PLAN_LIMITS, plan_limits_map
from billing.services import subscription_for
from console import audit
from console.models import AdminAuditLog
from console.permissions import AdminAPIView, IsAdminUser, IsFinanceAdmin
from console.serializers_subscription import (
    CompSerializer,
    ExtendTrialSerializer,
    ReasonSerializer,
    SubscriptionAuditLogSerializer,
    SubscriptionPatchSerializer,
    SubscriptionSerializer,
)
from core.models import Merchant


def _downgrade_shortfall(merchant: Merchant, new_plan: str) -> dict[str, dict[str, int]]:
    """``{capability: {usage, limit}}`` for any usage that exceeds ``new_plan``'s
    limits — the guardrail against silently dropping a merchant below their
    current usage (Phase 4 DoD)."""
    limits = plan_limits_map().get(new_plan) or PLAN_LIMITS[new_plan]
    usage = entitlements.usage(merchant)
    shortfall: dict[str, dict[str, int]] = {}
    for cap in LIMIT_CAPABILITIES:
        limit = limits[cap]
        if limit is None:
            continue
        assert isinstance(limit, int)  # LIMIT_CAPABILITIES values are int|None
        used = usage[cap.removeprefix("max_")]
        assert used is not None  # cards/locations/staff/customers are always counted
        if used > limit:
            shortfall[cap] = {"usage": used, "limit": limit}
    return shortfall


class MerchantSubscriptionView(AdminAPIView):
    """GET /merchants/{id}/subscription — state. PATCH — edit plan/status/override."""

    def get_permissions(self):
        classes = [IsAdminUser, IsFinanceAdmin] if self.request.method == "PATCH" else [IsAdminUser]
        return [cls() for cls in classes]

    @extend_schema(responses=SubscriptionSerializer)
    def get(self, request: Request, merchant_id: str) -> Response:
        mer = get_object_or_404(Merchant, pk=merchant_id)
        return Response(SubscriptionSerializer(subscription_for(mer)).data)

    @extend_schema(request=SubscriptionPatchSerializer, responses=SubscriptionSerializer)
    def patch(self, request: Request, merchant_id: str) -> Response:
        mer = get_object_or_404(Merchant, pk=merchant_id)
        body = SubscriptionPatchSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        sub = subscription_for(mer)
        before = SubscriptionSerializer(sub).data

        new_plan = data.get("plan")
        if new_plan and new_plan != sub.plan and not data.get("force"):
            shortfall = _downgrade_shortfall(mer, new_plan)
            if shortfall:
                return Response(
                    {
                        "error": {
                            "code": "PLAN_DOWNGRADE_BLOCKED",
                            "message": "Merchant's current usage exceeds the new plan's limits.",
                            "shortfall": shortfall,
                        }
                    },
                    status=409,
                )

        if new_plan:
            services.activate_plan(mer, new_plan)
            sub.refresh_from_db()
        # Applied after activate_plan so an explicit status in the same request
        # (e.g. re-activating into LOCKED) wins over activate_plan's default ACTIVE.
        if "status" in data:
            sub.status = data["status"]
        for field in ("override_plan", "override_expires_at", "notes"):
            if field in data:
                setattr(sub, field, data[field])
        sub.save()

        after = SubscriptionSerializer(sub).data
        audit.record(
            request,
            "subscription.update",
            target_type="subscription",
            target_id=str(mer.id),
            metadata={"reason": data["reason"], "before": before, "after": after},
        )
        return Response(after)


class ExtendTrialView(AdminAPIView):
    """POST /merchants/{id}/subscription/extend-trial {days}."""

    permission_classes = [IsAdminUser, IsFinanceAdmin]

    @extend_schema(request=ExtendTrialSerializer, responses=SubscriptionSerializer)
    def post(self, request: Request, merchant_id: str) -> Response:
        mer = get_object_or_404(Merchant, pk=merchant_id)
        body = ExtendTrialSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        days = body.validated_data["days"]

        before = SubscriptionSerializer(subscription_for(mer)).data
        sub = services.extend_trial(mer, days)
        after = SubscriptionSerializer(sub).data

        audit.record(
            request,
            "subscription.extend_trial",
            target_type="subscription",
            target_id=str(mer.id),
            metadata={
                "days": days,
                "reason": body.validated_data.get("reason", ""),
                "before": before,
                "after": after,
            },
        )
        return Response(after)


class CompView(AdminAPIView):
    """POST /merchants/{id}/subscription/comp {on, reason}."""

    permission_classes = [IsAdminUser, IsFinanceAdmin]

    @extend_schema(request=CompSerializer, responses=SubscriptionSerializer)
    def post(self, request: Request, merchant_id: str) -> Response:
        mer = get_object_or_404(Merchant, pk=merchant_id)
        body = CompSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        on = body.validated_data["on"]

        before = SubscriptionSerializer(subscription_for(mer)).data
        sub = services.set_comp(mer, on)
        after = SubscriptionSerializer(sub).data

        audit.record(
            request,
            "subscription.comp",
            target_type="subscription",
            target_id=str(mer.id),
            metadata={
                "on": on,
                "reason": body.validated_data["reason"],
                "before": before,
                "after": after,
            },
        )
        return Response(after)


class LockView(AdminAPIView):
    """POST /merchants/{id}/subscription/lock {reason}."""

    permission_classes = [IsAdminUser, IsFinanceAdmin]

    @extend_schema(request=ReasonSerializer, responses=SubscriptionSerializer)
    def post(self, request: Request, merchant_id: str) -> Response:
        mer = get_object_or_404(Merchant, pk=merchant_id)
        body = ReasonSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        before = SubscriptionSerializer(subscription_for(mer)).data
        sub = services.lock(mer)
        after = SubscriptionSerializer(sub).data

        audit.record(
            request,
            "subscription.lock",
            target_type="subscription",
            target_id=str(mer.id),
            metadata={"reason": body.validated_data["reason"], "before": before, "after": after},
        )
        return Response(after)


class UnlockView(AdminAPIView):
    """POST /merchants/{id}/subscription/unlock {reason}."""

    permission_classes = [IsAdminUser, IsFinanceAdmin]

    @extend_schema(request=ReasonSerializer, responses=SubscriptionSerializer)
    def post(self, request: Request, merchant_id: str) -> Response:
        mer = get_object_or_404(Merchant, pk=merchant_id)
        body = ReasonSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        before = SubscriptionSerializer(subscription_for(mer)).data
        sub = services.unlock(mer)
        after = SubscriptionSerializer(sub).data

        audit.record(
            request,
            "subscription.unlock",
            target_type="subscription",
            target_id=str(mer.id),
            metadata={"reason": body.validated_data["reason"], "before": before, "after": after},
        )
        return Response(after)


class SubscriptionAuditView(AdminAPIView):
    """GET /merchants/{id}/subscription/audit — recent subscription changes."""

    @extend_schema(responses=SubscriptionAuditLogSerializer(many=True))
    def get(self, request: Request, merchant_id: str) -> Response:
        logs = AdminAuditLog.objects.filter(target_type="subscription", target_id=str(merchant_id))[
            :20
        ]
        return Response(SubscriptionAuditLogSerializer(logs, many=True).data)
