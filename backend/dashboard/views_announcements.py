"""Merchant-facing in-app announcements (Phase 10).

The dashboard reads its unread/recent announcements here and marks one read.
Delivery rows are created admin-side when an announcement is sent to a segment
this merchant belongs to (``console.AnnouncementDelivery``).
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsScannerOrAbove
from console.models import AnnouncementDelivery
from core.tenancy import get_request_merchant


class InAppAnnouncementSerializer(serializers.Serializer):
    id = serializers.UUIDField()  # delivery id (what /read takes)
    title = serializers.CharField(source="announcement.title")
    body = serializers.CharField(source="announcement.body")
    sent_at = serializers.DateTimeField(source="announcement.sent_at")
    read = serializers.SerializerMethodField()

    def get_read(self, obj: AnnouncementDelivery) -> bool:
        return obj.read_at is not None


class AnnouncementListView(APIView):
    """GET /announcements — this merchant's in-app announcements (recent first)."""

    permission_classes = [IsScannerOrAbove]

    @extend_schema(responses=InAppAnnouncementSerializer(many=True))
    def get(self, request: Request) -> Response:
        merchant = get_request_merchant(request)
        rows = (
            AnnouncementDelivery.objects.filter(merchant=merchant)
            .select_related("announcement")
            .order_by("-created_at")[:50]
        )
        return Response(InAppAnnouncementSerializer(rows, many=True).data)


class AnnouncementReadView(APIView):
    """POST /announcements/{id}/read — mark a delivery read (open stat)."""

    permission_classes = [IsScannerOrAbove]

    @extend_schema(request=None, responses=None)
    def post(self, request: Request, delivery_id: str) -> Response:
        merchant = get_request_merchant(request)
        delivery = get_object_or_404(AnnouncementDelivery, pk=delivery_id, merchant=merchant)
        if delivery.read_at is None:
            delivery.read_at = timezone.now()
            delivery.save(update_fields=["read_at"])
        return Response({"ok": True})
