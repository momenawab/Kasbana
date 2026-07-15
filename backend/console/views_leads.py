"""Admin console views for inbound "Get started" leads.

Any active admin may view the list and mark a lead contacted or delete it. The
public intake that creates these lives in ``console.public``.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from console import audit
from console.models import Lead
from console.permissions import AdminAPIView
from console.serializers_leads import LeadSerializer


class LeadListView(AdminAPIView):
    """GET /leads — every inbound lead, newest first."""

    @extend_schema(responses=LeadSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(LeadSerializer(Lead.objects.all(), many=True).data)


class LeadDetailView(AdminAPIView):
    """PATCH /leads/{id} — toggle contacted status · DELETE /leads/{id}."""

    @extend_schema(request=None, responses=LeadSerializer)
    def patch(self, request: Request, lead_id: str) -> Response:
        lead = get_object_or_404(Lead, pk=lead_id)
        status = (request.data.get("status") or Lead.Status.CONTACTED).strip()
        if status not in Lead.Status.values:
            return Response(
                {"error": {"code": "INVALID_STATUS", "message": "Unknown lead status."}},
                status=400,
            )
        lead.status = status
        lead.contacted_at = timezone.now() if status == Lead.Status.CONTACTED else None
        lead.save(update_fields=["status", "contacted_at", "updated_at"])
        audit.record(
            request,
            "lead.update",
            target_type="lead",
            target_id=str(lead.id),
            metadata={"status": lead.status, "business_name": lead.business_name},
        )
        return Response(LeadSerializer(lead).data)

    @extend_schema(responses=None)
    def delete(self, request: Request, lead_id: str) -> Response:
        lead = get_object_or_404(Lead, pk=lead_id)
        audit.record(
            request,
            "lead.delete",
            target_type="lead",
            target_id=str(lead.id),
            metadata={"business_name": lead.business_name, "email": lead.email},
        )
        lead.delete()
        return Response(status=204)
