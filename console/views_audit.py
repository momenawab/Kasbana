"""Audit-log viewer endpoints (Phase 13).

Answers "who did what?". Both endpoints are **reads** over the append-only
``AdminAuditLog`` spine, so they follow the console convention of staying open to
any active admin (Read-only admins audit the platform — that's their job). The
matrix only gates *mutations*, and nothing here mutates.
"""

from __future__ import annotations

import csv

from django.db.models import QuerySet
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from common.pagination import DefaultCursorPagination
from console.models import AdminAuditLog
from console.permissions import AdminAPIView
from console.serializers_audit import AuditLogSerializer

_FILTER_PARAMS = [
    OpenApiParameter("actor", str, description="Actor email contains"),
    OpenApiParameter("action", str, description="Action key contains (e.g. merchant.suspend)"),
    OpenApiParameter("target_type", str, description="Exact target type (e.g. merchant)"),
    OpenApiParameter("target_id", str, description="Exact target id"),
    OpenApiParameter("from", str, description="From date YYYY-MM-DD (inclusive)"),
    OpenApiParameter("to", str, description="To date YYYY-MM-DD (inclusive)"),
]


def filtered_events(params: dict) -> QuerySet[AdminAuditLog]:
    """Apply the viewer's filters to the audit spine (all optional, AND-combined)."""
    qs = AdminAuditLog.objects.all()
    if actor := params.get("actor"):
        qs = qs.filter(actor_email__icontains=actor)
    if action := params.get("action"):
        qs = qs.filter(action__icontains=action)
    if target_type := params.get("target_type"):
        qs = qs.filter(target_type=target_type)
    if target_id := params.get("target_id"):
        qs = qs.filter(target_id=target_id)
    if raw_from := params.get("from"):
        if (d := parse_date(raw_from)) is not None:
            qs = qs.filter(created_at__date__gte=d)
    if raw_to := params.get("to"):
        if (d := parse_date(raw_to)) is not None:
            qs = qs.filter(created_at__date__lte=d)
    return qs


class AuditLogListView(AdminAPIView):
    """GET /audit — filter the admin audit trail (any admin, paginated)."""

    @extend_schema(parameters=_FILTER_PARAMS, responses=AuditLogSerializer(many=True))
    def get(self, request: Request) -> Response:
        qs = filtered_events(request.query_params)
        paginator = DefaultCursorPagination()
        page = paginator.paginate_queryset(qs, request, view=self) or []
        return paginator.get_paginated_response(AuditLogSerializer(page, many=True).data)


class AuditLogExportView(AdminAPIView):
    """GET /audit/export — the filtered trail as CSV (any admin)."""

    @extend_schema(parameters=_FILTER_PARAMS, responses={(200, "text/csv"): bytes})
    def get(self, request: Request) -> HttpResponse:
        qs = filtered_events(request.query_params)
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="audit_log.csv"'
        writer = csv.writer(response)
        writer.writerow(["created_at", "actor_email", "action", "target_type", "target_id", "ip"])
        for e in qs.iterator():
            writer.writerow(
                [
                    e.created_at.isoformat(),
                    e.actor_email,
                    e.action,
                    e.target_type,
                    e.target_id,
                    e.ip,
                ]
            )
        return response
