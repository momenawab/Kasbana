"""Registration-theme editor endpoints (Phase 1 · finalize-phases).

- GET/PATCH  /settings/enroll-theme            — the merchant-wide default theme.
- GET/PATCH/DELETE  /cards/{id}/enroll-theme   — a per-card override. GET returns
  the *inherited* values (merchant default) with ``is_override=false`` until the
  merchant explicitly saves one; PATCH creates/updates it; DELETE clears it (the
  card falls back to the merchant default). GET must NOT auto-create a row, or a
  stock override would shadow the merchant's customized default in resolve_theme.

All scoped to the caller's merchant; owner/manager only (``CanManageCards``).
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from branding.models import RegistrationTheme
from branding.serializers import RegistrationThemeSerializer
from common.permissions import CanManageCards
from core.models import Card
from core.tenancy import get_request_merchant, get_scoped


class MerchantEnrollThemeView(generics.RetrieveUpdateAPIView):
    """The merchant-wide default enroll theme (created on first access)."""

    serializer_class = RegistrationThemeSerializer
    permission_classes = [CanManageCards]
    http_method_names = ["get", "patch"]

    def get_object(self) -> RegistrationTheme:
        merchant = get_request_merchant(self.request)
        obj, _ = RegistrationTheme.objects.get_or_create(merchant=merchant, card=None)
        return obj


class CardEnrollThemeView(APIView):
    """A per-card override; inherits the merchant default until explicitly saved."""

    permission_classes = [CanManageCards]
    serializer_class = RegistrationThemeSerializer

    @extend_schema(responses=RegistrationThemeSerializer)
    def get(self, request: Request, card_id: str) -> Response:
        merchant = get_request_merchant(request)
        get_scoped(Card, request, pk=card_id)  # 404s across tenants
        row = RegistrationTheme.objects.filter(merchant=merchant, card_id=card_id).first()
        if row is not None:
            data = dict(RegistrationThemeSerializer(row).data)
            data["is_override"] = True
        else:
            default = RegistrationTheme.objects.filter(merchant=merchant, card__isnull=True).first()
            source = default if default is not None else RegistrationTheme()
            data = dict(RegistrationThemeSerializer(source).data)
            data["is_override"] = False
        return Response(data)

    @extend_schema(request=RegistrationThemeSerializer, responses=RegistrationThemeSerializer)
    def patch(self, request: Request, card_id: str) -> Response:
        merchant = get_request_merchant(request)
        card = get_scoped(Card, request, pk=card_id)
        row, _ = RegistrationTheme.objects.get_or_create(merchant=merchant, card=card)
        ser = RegistrationThemeSerializer(row, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        data = dict(ser.data)
        data["is_override"] = True
        return Response(data)

    def delete(self, request: Request, card_id: str) -> Response:
        merchant = get_request_merchant(request)
        get_scoped(Card, request, pk=card_id)
        RegistrationTheme.objects.filter(merchant=merchant, card_id=card_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
