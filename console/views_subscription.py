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
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from billing import entitlements, services
from billing.models import Plan
from billing.plans import LIMIT_CAPABILITIES, plan_price
from billing.services import subscription_for
from console import audit
from console.models import AdminAuditLog
from console.permissions import AdminAPIView, IsAdminUser, IsFinanceAdmin
from console.serializers_subscription import (
    AssignEnterpriseSerializer,
    CompSerializer,
    EnterpriseAssignmentSerializer,
    ExtendTrialSerializer,
    ReasonSerializer,
    SubscriptionAuditLogSerializer,
    SubscriptionPatchSerializer,
    SubscriptionSerializer,
)
from core.models import Merchant

# capability -> the key ``entitlements.usage()`` reports it under. Mostly the
# capability minus "max_", but not always: the campaign allowance is per-month,
# so its usage key says so and a blind removeprefix() would KeyError.
_USAGE_KEYS = {
    "max_cards": "cards",
    "max_locations": "locations",
    "max_staff": "staff",
    "max_customers": "customers",
    "max_campaigns_per_month": "campaigns_this_month",
}


def _downgrade_shortfall(merchant: Merchant, new_plan: str) -> dict[str, dict[str, int]]:
    """``{capability: {usage, limit}}`` for any usage that exceeds ``new_plan``'s
    limits — the guardrail against silently dropping a merchant below their
    current usage (Phase 4 DoD)."""
    # Shares the entitlements engine's resolution so a key with no catalogue row
    # (ENTERPRISE — the tier, whose row is the negotiated plan) reads as
    # deny-all rather than raising KeyError mid-request.
    limits = entitlements._limits_for(new_plan)
    usage = entitlements.usage(merchant)
    shortfall: dict[str, dict[str, int]] = {}
    for cap in LIMIT_CAPABILITIES:
        limit = limits[cap]
        if limit is None:
            continue
        assert isinstance(limit, int)  # LIMIT_CAPABILITIES values are int|None
        used = usage[_USAGE_KEYS[cap]]
        assert used is not None
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

        # Only a genuine plan CHANGE goes through activate_plan — the client re-sends
        # the current plan on every save (e.g. an override/notes-only edit), and
        # activate_plan resets current_period_end, so calling it for an unchanged
        # plan would silently wipe a paying merchant's renewal date.
        plan_changed = "plan" in data and data["plan"] != sub.plan
        if plan_changed and not data.get("force"):
            shortfall = _downgrade_shortfall(mer, data["plan"])
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

        if plan_changed:
            services.activate_plan(mer, data["plan"])
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


class AssignEnterpriseView(AdminAPIView):
    """POST /merchants/{id}/subscription/enterprise {plan_key, interval, reason}.

    Step 4 of the Enterprise flow (§12): sales agreed terms, an admin now puts
    the merchant on the matching plan.

    Records the agreement only — it does not grant access or charge anyone. The
    merchant pays through the ordinary checkout (`POST /billing/subscribe`,
    which resolves their negotiated plan server-side) and activates on the
    payment webhook exactly like a self-serve merchant. That is the whole point
    of §12.3: no second payment path to maintain.
    """

    permission_classes = [IsAdminUser, IsFinanceAdmin]

    @extend_schema(request=AssignEnterpriseSerializer, responses=EnterpriseAssignmentSerializer)
    def post(self, request: Request, merchant_id: str) -> Response:
        mer = get_object_or_404(Merchant, pk=merchant_id)
        body = AssignEnterpriseSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        plan = get_object_or_404(Plan, key=data["plan_key"])
        before = SubscriptionSerializer(subscription_for(mer)).data
        try:
            sub = services.assign_enterprise_plan(mer, plan, interval=data["interval"])
        except ValueError as exc:
            # A public or archived plan — the service is the authority on what
            # may be negotiated; surface its reason rather than a 500.
            raise DRFValidationError({"plan_key": str(exc)}) from exc

        after = SubscriptionSerializer(sub).data
        audit.record(
            request,
            "subscription.assign_enterprise",
            target_type="subscription",
            target_id=str(mer.id),
            metadata={"reason": data["reason"], "before": before, "after": after},
        )
        return Response(
            EnterpriseAssignmentSerializer(
                {
                    "plan_key": plan.key,
                    "plan_name": plan.name,
                    "price_egp": plan_price(plan.key, data["interval"]),
                    "interval": data["interval"],
                    "subscription": sub,
                }
            ).data
        )


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
