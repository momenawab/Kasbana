"""Admin console views for inbound support/contact messages.

Any active admin may view the list and mark a message read/unread or delete it.
The public intake that creates these lives in ``console.public``.
"""

from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from console import audit
from console.models import ContactMessage
from console.permissions import AdminAPIView
from console.serializers_contact import (
    AdminContactMessageCreateSerializer,
    ContactMessageSerializer,
    ContactReplySerializer,
)


class ContactMessageListView(AdminAPIView):
    """GET /messages — list · POST /messages — admin-created message."""

    @extend_schema(responses=ContactMessageSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(ContactMessageSerializer(ContactMessage.objects.all(), many=True).data)

    @extend_schema(request=AdminContactMessageCreateSerializer, responses=ContactMessageSerializer)
    def post(self, request: Request) -> Response:
        """Create a contact message manually so the admin can then reply to it."""
        serializer = AdminContactMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        audit.record(
            request,
            "contact_message.create",
            target_type="contact_message",
            target_id=str(message.id),
            metadata={"email": message.email, "subject": message.subject},
        )
        return Response(ContactMessageSerializer(message).data, status=201)


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


class ContactReplyView(AdminAPIView):
    """POST /messages/{id}/reply — email the sender a branded reply.

    Renders the Stampn reply template (dark HTML + plain-text fallback) with the
    admin's free-text ``message`` and sends it to the original sender via the
    configured SMTP backend, then marks the message ``Replied`` and audits it.
    """

    @extend_schema(request=ContactReplySerializer, responses=ContactMessageSerializer)
    def post(self, request: Request, message_id: str) -> Response:
        message = get_object_or_404(ContactMessage, pk=message_id)
        serializer = ContactReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data["message"]

        context = {"customer_name": message.name, "body": body}
        text_body = render_to_string("email/contact_reply.txt", context)
        html_body = render_to_string("email/contact_reply.html", context)
        subject = f"Re: {message.subject}" if message.subject else "Re: your message to Stampn"

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            to=[message.email],
            reply_to=[settings.EMAIL_HOST_USER] if settings.EMAIL_HOST_USER else None,
        )
        email.attach_alternative(html_body, "text/html")
        try:
            email.send(fail_silently=False)
        except Exception as exc:  # noqa: BLE001 - surface any SMTP/backend failure to the admin
            return Response(
                {"error": {"code": "EMAIL_SEND_FAILED", "message": str(exc)}},
                status=502,
            )

        message.status = ContactMessage.Status.REPLIED
        message.replied_at = timezone.now()
        message.save(update_fields=["status", "replied_at", "updated_at"])
        audit.record(
            request,
            "contact_message.reply",
            target_type="contact_message",
            target_id=str(message.id),
            metadata={"email": message.email, "subject": message.subject},
        )
        return Response(ContactMessageSerializer(message).data)
