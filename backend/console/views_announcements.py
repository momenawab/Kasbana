"""Announcement endpoints (Phase 10).

Broadcasts are high-visibility → create/edit/delete/send/schedule are gated to
**Super-admin / Marketing-admin** (``IsMarketingAdmin``); list/detail/preview are
open to any admin. Every send + schedule is audited. A DRAFT/SCHEDULED
announcement is editable; a SENT one is immutable.
"""

from __future__ import annotations

from typing import cast

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from console import announcements as ann
from console import audit
from console.models import AdminUser, Announcement
from console.permissions import AdminAPIView, IsAdminUser, IsMarketingAdmin
from console.serializers_announcements import (
    AnnouncementSerializer,
    AnnouncementWriteSerializer,
    AudiencePreviewSerializer,
)


class AnnouncementListView(AdminAPIView):
    """GET /announcements (any admin) · POST create draft (Marketing+)."""

    def get_permissions(self):
        classes = [IsAdminUser] if self.request.method == "GET" else [IsAdminUser, IsMarketingAdmin]
        return [cls() for cls in classes]

    @extend_schema(responses=AnnouncementSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(AnnouncementSerializer(Announcement.objects.all(), many=True).data)

    @extend_schema(request=AnnouncementWriteSerializer, responses=AnnouncementSerializer)
    def post(self, request: Request) -> Response:
        body = AnnouncementWriteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        announcement = body.save(created_by=cast(AdminUser, request.user))
        audit.record(
            request,
            "announcement.create",
            target_type="announcement",
            target_id=str(announcement.id),
            metadata={"title": announcement.title, "audience": announcement.audience},
        )
        return Response(AnnouncementSerializer(announcement).data, status=201)


class AnnouncementDetailView(AdminAPIView):
    """GET (any admin) · PATCH / DELETE (Marketing+, DRAFT/SCHEDULED only)."""

    def get_permissions(self):
        classes = [IsAdminUser] if self.request.method == "GET" else [IsAdminUser, IsMarketingAdmin]
        return [cls() for cls in classes]

    @extend_schema(responses=AnnouncementSerializer)
    def get(self, request: Request, announcement_id: str) -> Response:
        return Response(
            AnnouncementSerializer(get_object_or_404(Announcement, pk=announcement_id)).data
        )

    @extend_schema(request=AnnouncementWriteSerializer, responses=AnnouncementSerializer)
    def patch(self, request: Request, announcement_id: str) -> Response:
        announcement = get_object_or_404(Announcement, pk=announcement_id)
        if announcement.status == Announcement.Status.SENT:
            return Response(
                {
                    "error": {
                        "code": "ANNOUNCEMENT_SENT",
                        "message": "A sent announcement is immutable.",
                    }
                },
                status=409,
            )
        body = AnnouncementWriteSerializer(announcement, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        body.save()
        return Response(AnnouncementSerializer(announcement).data)

    @extend_schema(responses=None)
    def delete(self, request: Request, announcement_id: str) -> Response:
        announcement = get_object_or_404(Announcement, pk=announcement_id)
        if announcement.status == Announcement.Status.SENT:
            return Response(
                {
                    "error": {
                        "code": "ANNOUNCEMENT_SENT",
                        "message": "A sent announcement can't be deleted.",
                    }
                },
                status=409,
            )
        announcement.delete()
        return Response(status=204)


class AnnouncementSendView(AdminAPIView):
    """POST /announcements/{id}/send — deliver now (Marketing+)."""

    permission_classes = [IsAdminUser, IsMarketingAdmin]

    @extend_schema(request=None, responses=AnnouncementSerializer)
    def post(self, request: Request, announcement_id: str) -> Response:
        announcement = get_object_or_404(Announcement, pk=announcement_id)
        if announcement.status == Announcement.Status.SENT:
            return Response(
                {"error": {"code": "ANNOUNCEMENT_SENT", "message": "Already sent."}}, status=409
            )
        result = ann.send(announcement)
        audit.record(
            request,
            "announcement.send",
            target_type="announcement",
            target_id=str(announcement.id),
            metadata={"title": announcement.title, **result},
        )
        return Response(AnnouncementSerializer(announcement).data)


class AnnouncementScheduleView(AdminAPIView):
    """POST /announcements/{id}/schedule — mark SCHEDULED (Marketing+).

    Requires ``schedule_at`` to be set (via create/patch); the beat task
    ``console.tasks.send_due_announcements`` delivers it when due.
    """

    permission_classes = [IsAdminUser, IsMarketingAdmin]

    @extend_schema(request=None, responses=AnnouncementSerializer)
    def post(self, request: Request, announcement_id: str) -> Response:
        announcement = get_object_or_404(Announcement, pk=announcement_id)
        if announcement.status == Announcement.Status.SENT:
            return Response(
                {"error": {"code": "ANNOUNCEMENT_SENT", "message": "Already sent."}}, status=409
            )
        if announcement.schedule_at is None or announcement.schedule_at <= timezone.now():
            return Response(
                {
                    "error": {
                        "code": "INVALID_SCHEDULE",
                        "message": "Set schedule_at to a future time before scheduling.",
                    }
                },
                status=400,
            )
        announcement.status = Announcement.Status.SCHEDULED
        announcement.save(update_fields=["status", "updated_at"])
        audit.record(
            request,
            "announcement.schedule",
            target_type="announcement",
            target_id=str(announcement.id),
            metadata={"schedule_at": announcement.schedule_at.isoformat()},
        )
        return Response(AnnouncementSerializer(announcement).data)


class AudiencePreviewView(AdminAPIView):
    """GET /announcements/audience-preview?audience=&param= — recipient count."""

    @extend_schema(
        parameters=[
            OpenApiParameter("audience", str, description="all|plan|trial_ending|at_risk|active"),
            OpenApiParameter("param", str, description="plan key for the 'plan' segment"),
        ],
        responses=AudiencePreviewSerializer,
    )
    def get(self, request: Request) -> Response:
        audience = (request.query_params.get("audience") or "all").strip()
        param = (request.query_params.get("param") or "").strip()
        return Response({"recipients": ann.audience_count(audience, param)})
