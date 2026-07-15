"""Merchant support — a logged-in merchant reaches the team (finalize Phase B).

``GET  /support/messages`` — this merchant's own support messages + statuses.
``POST /support/messages`` — open a new support message.

The message is stored as a ``console.ContactMessage`` with ``source=dashboard``
and ``merchant`` set, so it lands both in the admin global inbox and on this
merchant's admin Support tab, where support replies via the existing branded
email flow. The sender name/email are taken from the authenticated user — never
the request body — so one merchant can't submit under another's identity.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsScannerOrAbove
from console.models import ContactMessage
from core.tenancy import get_request_merchant


class MerchantSupportMessageSerializer(serializers.ModelSerializer):
    """Read shape for the merchant's own list — no name/email echo needed."""

    class Meta:
        model = ContactMessage
        fields = ["id", "subject", "message", "status", "replied_at", "created_at"]
        read_only_fields = fields


class MerchantSupportCreateSerializer(serializers.Serializer):
    """Write shape — only the content. Identity comes from the session."""

    subject = serializers.CharField(max_length=200, trim_whitespace=True)
    message = serializers.CharField(min_length=1, trim_whitespace=True)


class MerchantSupportMessagesView(APIView):
    """GET + POST /support/messages — this merchant's support thread."""

    permission_classes = [IsScannerOrAbove]
    # A compromised account can't flood the support queue past this rate.
    throttle_scope = "support_message"

    def get_throttles(self):
        # Only the POST is worth throttling; a merchant reading their own list
        # shouldn't be rate-limited.
        if self.request.method == "POST":
            return super().get_throttles()
        return []

    @extend_schema(responses=MerchantSupportMessageSerializer(many=True))
    def get(self, request: Request) -> Response:
        merchant = get_request_merchant(request)
        rows = ContactMessage.objects.filter(merchant=merchant).order_by("-created_at")[:50]
        return Response(MerchantSupportMessageSerializer(rows, many=True).data)

    @extend_schema(
        request=MerchantSupportCreateSerializer, responses=MerchantSupportMessageSerializer
    )
    def post(self, request: Request) -> Response:
        merchant = get_request_merchant(request)
        body = MerchantSupportCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        staff = request.staff  # type: ignore[attr-defined]  # set by auth, non-null here
        message = ContactMessage.objects.create(
            merchant=merchant,
            source=ContactMessage.Source.DASHBOARD,
            # Identity from the session, never the request body.
            name=(staff.user.get_full_name() or merchant.name),
            email=staff.user.email,
            subject=body.validated_data["subject"],
            message=body.validated_data["message"],
        )
        return Response(MerchantSupportMessageSerializer(message).data, status=201)
