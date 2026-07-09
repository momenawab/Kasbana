"""Admin console views for inbound support/contact messages.

Any active admin may view the list and mark a message read/unread or delete it.
The public intake that creates these lives in ``console.public``.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from console import audit
from console.models import ContactMessage
from console.permissions import AdminAPIView
from console.serializers_contact import ContactMessageSerializer


class ContactMessageListView(AdminAPIView):
    """GET /messages — every inbound contact message, newest first."""

    @extend_schema(responses=ContactMessageSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(ContactMessageSerializer(ContactMessage.objects.all(), many=True).data)


class ContactMessageDetailView(AdminAPIView):
    """PATCH /messages/{id} — toggle read status · DELETE /messages/{id}."""

    @extend_schema(request=None, responses=ContactMessageSerializer)
    def patch(self, request: Request, message_id: str) -> Response:
        message = get_object_or_404(ContactMessage, pk=message_id)
        status = (request.data.get("status") or ContactMessage.Status.READ).strip()
        if status not in ContactMessage.Status.values:
            return Response(
                {"error": {"code": "INVALID_STATUS", "message": "Unknown message status."}},
                status=400,
            )
        message.status = status
        message.read_at = timezone.now() if status == ContactMessage.Status.READ else None
        message.save(update_fields=["status", "read_at", "updated_at"])
        audit.record(
            request,
            "contact_message.update",
            target_type="contact_message",
            target_id=str(message.id),
            metadata={"status": message.status, "subject": message.subject},
        )
        return Response(ContactMessageSerializer(message).data)

    @extend_schema(responses=None)
    def delete(self, request: Request, message_id: str) -> Response:
        message = get_object_or_404(ContactMessage, pk=message_id)
        audit.record(
            request,
            "contact_message.delete",
            target_type="contact_message",
            target_id=str(message.id),
            metadata={"subject": message.subject, "email": message.email},
        )
        message.delete()
        return Response(status=204)
