from __future__ import annotations

import hmac

from django.conf import settings
from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import SendOTPSerializer, VerifyOTPSerializer
from .services import OTPService
from .webhook import process, valid_signature


class SendWhatsAppOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        body = SendOTPSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        OTPService().send_otp(body.validated_data["phone"])
        return Response({"success": True})


class VerifyWhatsAppOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        body = VerifyOTPSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(OTPService().verify_otp(**body.validated_data))


class WhatsAppWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request: Request) -> HttpResponse:
        # Meta compares the response body byte-for-byte with the challenge it
        # sent. DRF's Response still runs the JSONRenderer even when handed
        # content_type="text/plain", so it returns `"1158201444"` WITH quotes and
        # Meta rejects the subscription ("callback URL or verify token couldn't
        # be validated") despite the 200. A bare HttpResponse skips the renderer
        # and emits the raw digits.
        token = settings.WHATSAPP_VERIFY_TOKEN or ""
        if (
            token
            and request.query_params.get("hub.mode") == "subscribe"
            and hmac.compare_digest(request.query_params.get("hub.verify_token", ""), token)
        ):
            return HttpResponse(
                request.query_params.get("hub.challenge", ""), content_type="text/plain"
            )
        # Fail closed: an unset token must never validate an empty query param.
        return HttpResponse(status=403)

    def post(self, request: Request) -> Response:
        if not valid_signature(request.body, request.headers.get("X-Hub-Signature-256", "")):
            return Response(status=401)
        process(request.data)
        return Response(status=200)
