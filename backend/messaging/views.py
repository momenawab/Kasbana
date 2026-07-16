"""Engage + messaging endpoints (contract §3.6 · Phase 1.7).

Campaigns (list / create+send-or-schedule), computed segments, automations
(list / toggle), and the one-off ``POST /customers/{id}/message``. Delivery is
the free wallet push channel; the automation enabled-count is gated by the
plan's ``automations`` allowance.
"""

from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from billing import entitlements
from billing.plans import PLAN_LIMITS, plan_limits_map
from billing.services import subscription_for
from common.errors import PlanLimit, UnprocessableEntity
from common.permissions import CanEngage
from core.models import CustomerCard
from core.tenancy import get_request_merchant, get_scoped
from messaging import segments
from messaging.enums import AutomationKey, CampaignStatus
from messaging.models import Automation, Campaign
from messaging.serializers import (
    AUTOMATION_KEYS,
    AutomationSerializer,
    AutomationWriteSerializer,
    CampaignSerializer,
    CampaignWriteSerializer,
    CustomerMessageSerializer,
    SegmentSerializer,
)


# ── Campaigns ─────────────────────────────────────────────────────────────────
class CampaignListCreateView(generics.ListCreateAPIView):
    """GET /campaigns (paginated) · POST /campaigns (create + send/schedule)."""

    permission_classes = [CanEngage]

    def get_serializer_class(self) -> type[BaseSerializer]:
        return CampaignWriteSerializer if self.request.method == "POST" else CampaignSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return Campaign.objects.for_merchant(get_request_merchant(self.request))

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        body = CampaignWriteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        merchant = get_request_merchant(request)

        # Unlimited on every public tier, so this is a no-op there; it exists
        # for Enterprise plans, where the monthly allowance is negotiated.
        entitlements.enforce(merchant, "max_campaigns_per_month")

        schedule_at = data.get("schedule_at")
        scheduled = bool(schedule_at and schedule_at > timezone.now())
        campaign = Campaign.objects.create(
            merchant=merchant,
            audience=data["audience"],
            message=data["message"],
            schedule_at=schedule_at,
            status=CampaignStatus.SCHEDULED if scheduled else CampaignStatus.DRAFT,
        )

        if not scheduled:
            from messaging.tasks import send_campaign

            send_campaign.delay(str(campaign.id))
            campaign.refresh_from_db()

        return Response(CampaignSerializer(campaign).data, status=status.HTTP_201_CREATED)


# ── Segments ──────────────────────────────────────────────────────────────────
class SegmentListView(APIView):
    """GET /segments — computed audiences with live counts."""

    permission_classes = [CanEngage]
    serializer_class = SegmentSerializer

    @extend_schema(responses=SegmentSerializer(many=True))
    def get(self, request: Request) -> Response:
        merchant = get_request_merchant(request)
        results = segments.catalogue(merchant)
        return Response({"results": SegmentSerializer(results, many=True).data})


# ── Automations ───────────────────────────────────────────────────────────────
class AutomationListView(APIView):
    """GET /automations — every automation key, defaulting to disabled."""

    permission_classes = [CanEngage]
    serializer_class = AutomationSerializer

    @extend_schema(responses=AutomationSerializer(many=True))
    def get(self, request: Request) -> Response:
        merchant = get_request_merchant(request)
        existing = {a.key: a for a in Automation.objects.for_merchant(merchant)}
        results = []
        for key in AUTOMATION_KEYS:
            automation = existing.get(key)
            if automation is None:
                results.append({"key": key, "enabled": False, "timing": "", "template": ""})
            else:
                results.append(AutomationSerializer(automation).data)
        return Response({"results": results})


class AutomationDetailView(APIView):
    """PATCH /automations/{key} — toggle / configure one automation."""

    permission_classes = [CanEngage]
    serializer_class = AutomationSerializer

    @extend_schema(request=AutomationWriteSerializer, responses=AutomationSerializer)
    def patch(self, request: Request, key: str) -> Response:
        if key not in AUTOMATION_KEYS:
            raise UnprocessableEntity("Unknown automation key.")

        merchant = get_request_merchant(request)
        body = AutomationWriteSerializer(data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        automation, _ = Automation.objects.get_or_create(merchant=merchant, key=key)

        # `welcome` is transactional onboarding — free on every plan. Every other
        # (engagement) automation is a Growth+ feature; only gate turning one on.
        enabling = data.get("enabled", automation.enabled) and not automation.enabled
        if enabling and key != AutomationKey.WELCOME:
            self._enforce_engagement_automation(merchant)

        for field in ("enabled", "timing", "template"):
            if field in data:
                setattr(automation, field, data[field])
        automation.save()
        return Response(AutomationSerializer(automation).data)

    @staticmethod
    def _enforce_engagement_automation(merchant) -> None:  # type: ignore[no-untyped-def]
        """Engagement automations are Growth+. Starter's allowance is 0; the free
        `welcome` automation is excluded from the count so it never consumes it."""
        sub = subscription_for(merchant)
        plan = sub.effective_plan()
        if plan is None:  # locked
            raise PlanLimit("Your plan does not allow automations.")
        allowance = (plan_limits_map().get(plan) or PLAN_LIMITS[plan])["automations"]
        assert isinstance(allowance, int)
        enabled_count = (
            Automation.objects.for_merchant(merchant)
            .filter(enabled=True)
            .exclude(key=AutomationKey.WELCOME)
            .count()
        )
        if enabled_count >= allowance:
            raise PlanLimit("Automations are a Growth plan feature.")


# ── One-off customer message ──────────────────────────────────────────────────
class CustomerMessageView(APIView):
    """POST /customers/{id}/message — send a one-off wallet push message."""

    permission_classes = [CanEngage]
    serializer_class = CustomerMessageSerializer

    @extend_schema(request=CustomerMessageSerializer)
    def post(self, request: Request, customer_id: str) -> Response:
        body = CustomerMessageSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        text = body.validated_data["text"]

        customer = get_scoped(CustomerCard, request, pk=customer_id)
        # Free wallet notification (Apple changeMessage + Google addMessage).
        from wallets import service as wallet

        wallet.push_message(customer, text)
        return Response({"ok": True})
