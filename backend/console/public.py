"""Public (unauthenticated) endpoints backed by console models.

Only the marketing "Get started" lead intake lives here. It is deliberately
open (``AllowAny``, no auth) because it is called from the public marketing
site before anyone has an account. A honeypot field defends against bots.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from console.serializers_leads import LeadCreateSerializer


class LeadIntakeThrottle(AnonRateThrottle):
    scope = "lead_intake"


class PublicLeadCreateView(APIView):
    """POST /leads — capture a "Get started" lead from the marketing site."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [LeadIntakeThrottle]

    @extend_schema(request=LeadCreateSerializer, responses={201: None})
    def post(self, request: Request) -> Response:
        serializer = LeadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Honeypot: a bot fills this hidden field — accept silently, save nothing.
        if serializer.validated_data.get("botcheck"):
            return Response(status=201)

        serializer.save()
        return Response(status=201)
