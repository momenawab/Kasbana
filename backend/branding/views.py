"""Registration-theme editor endpoints (Phase 1 · finalize-phases).

- GET/PATCH  /settings/enroll-theme            — the merchant-wide default theme.
- GET/PATCH/DELETE  /cards/{id}/enroll-theme   — a per-card override (DELETE
  clears it, so the card falls back to the merchant default).

All scoped to the caller's merchant; owner/manager only (``CanManageCards``).
"""

from __future__ import annotations

from rest_framework import generics

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


class CardEnrollThemeView(generics.RetrieveUpdateDestroyAPIView):
    """A per-card override; DELETE removes it (falls back to the default)."""

    serializer_class = RegistrationThemeSerializer
    permission_classes = [CanManageCards]
    http_method_names = ["get", "patch", "delete"]

    def get_object(self) -> RegistrationTheme:
        card = get_scoped(Card, self.request, pk=self.kwargs["card_id"])
        merchant = get_request_merchant(self.request)
        obj, _ = RegistrationTheme.objects.get_or_create(merchant=merchant, card=card)
        return obj
