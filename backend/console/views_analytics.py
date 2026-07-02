"""Revenue & financial analytics endpoints (Phase 7).

``GET /analytics/revenue`` — the full KPI + series payload (JSON).
``GET /analytics/revenue/export`` — the monthly collected-revenue series as CSV.

Financials are sensitive: both are gated to **Finance/Super-admin** (hidden from
Support/Read-only), unlike the rest of the console where reads are open. Reads of
aggregate financials are not individually audited (no PII, no mutation).
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from console import analytics_revenue
from console.permissions import AdminAPIView, IsAdminUser, IsFinanceAdmin
from console.serializers_analytics import RevenueAnalyticsSerializer

DEFAULT_WINDOW_DAYS = 365


def _parse_range(params) -> tuple[date, date]:
    """Parse ``from``/``to`` (YYYY-MM-DD); default to the trailing 12 months."""
    today = date.today()

    def _parse(value: str) -> date | None:
        value = (value or "").strip()
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    date_to = _parse(params.get("to")) or today
    date_from = _parse(params.get("from")) or (date_to - timedelta(days=DEFAULT_WINDOW_DAYS))
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    return date_from, date_to


class RevenueAnalyticsView(AdminAPIView):
    """GET /analytics/revenue — Finance/Super-admin only."""

    permission_classes = [IsAdminUser, IsFinanceAdmin]

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str, description="Start date YYYY-MM-DD (default: 12mo ago)"),
            OpenApiParameter("to", str, description="End date YYYY-MM-DD (default: today)"),
        ],
        responses=RevenueAnalyticsSerializer,
    )
    def get(self, request: Request) -> Response:
        date_from, date_to = _parse_range(request.query_params)
        data = analytics_revenue.revenue_analytics(date_from, date_to)
        return Response(RevenueAnalyticsSerializer(data).data)


class RevenueExportView(AdminAPIView):
    """GET /analytics/revenue/export — monthly collected-revenue CSV (Finance)."""

    permission_classes = [IsAdminUser, IsFinanceAdmin]

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str, description="Start date YYYY-MM-DD"),
            OpenApiParameter("to", str, description="End date YYYY-MM-DD"),
        ],
        responses={(200, "text/csv"): bytes},
    )
    def get(self, request: Request) -> HttpResponse:
        date_from, date_to = _parse_range(request.query_params)
        data = analytics_revenue.revenue_analytics(date_from, date_to)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="revenue_{date_from.isoformat()}_{date_to.isoformat()}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(["month", "collected_egp", "paid_invoices", "new_payers"])
        for row in data["monthly_series"]:
            writer.writerow(
                [row["month"], row["collected_egp"], row["paid_invoices"], row["new_payers"]]
            )
        return response
