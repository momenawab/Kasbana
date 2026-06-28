"""Dashboard & analytics endpoints (contract §3.6 · Phase 3 · staff-auth).

Merchant configuration (cards, staff, locations), the customer list, and the
analytics summary. Every queryset is scoped to the caller's merchant via
``for_merchant`` / ``get_request_merchant`` so one merchant can never read or
mutate another's rows.

Judgment calls where the contract is silent (Phase 3):
- min role = Admin+ on all dashboard endpoints, except POST /staff which grants
  access and so requires Owner;
- Card CRUD exposes ``GET/POST /cards`` (list/create) and ``GET/PATCH
  /cards/{id}`` (the contract's "PATCH /cards" needs an id to target);
- create + update of a Card enqueue ``wallets.tasks.sync_google_class``;
- ``repeat_rate`` = share of customers with >= 2 STAMP events (returning).
"""

from __future__ import annotations

from typing import Any

from django.db.models import Count, Q, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from common.permissions import IsAdminOrAbove, IsOwner
from core.enums import CustomerCardStatus, LedgerEvent, WalletPlatform
from core.models import Card, CustomerCard, Location, Redemption, StaffUser, WalletRegistration
from core.tenancy import get_request_merchant
from dashboard.serializers import (
    AnalyticsSummarySerializer,
    CardSerializer,
    CustomerSerializer,
    LocationSerializer,
    StaffCreateSerializer,
    StaffSerializer,
)


def _enqueue_google_sync(card: Card) -> None:
    """Re-provision the Google LoyaltyClass after a Card create/edit (§4).

    Tests verify the task is *enqueued*; that the Google class is actually
    (re)provisioned needs Redis + a Celery worker + live Google creds — Momen's
    integration smoke test, not closable from inside this phase. The enqueue is
    not wrapped, so a Card create/update returns 500 if the broker is unreachable.
    """
    from wallets.tasks import sync_google_class

    sync_google_class.delay(str(card.id))


# ── Cards ─────────────────────────────────────────────────────────────────────
class CardListCreateView(generics.ListCreateAPIView):
    """GET /cards (list) · POST /cards (create)."""

    serializer_class = CardSerializer
    permission_classes = [IsAdminOrAbove]

    def get_queryset(self) -> QuerySet[Card]:
        return Card.objects.for_merchant(get_request_merchant(self.request)).order_by("-created_at")

    def perform_create(self, serializer: BaseSerializer) -> None:
        card = serializer.save(merchant=get_request_merchant(self.request))
        _enqueue_google_sync(card)


class CardDetailView(generics.RetrieveUpdateAPIView):
    """GET /cards/{id} · PATCH /cards/{id}."""

    serializer_class = CardSerializer
    permission_classes = [IsAdminOrAbove]
    http_method_names = ["get", "patch"]
    lookup_url_kwarg = "card_id"

    def get_queryset(self) -> QuerySet[Card]:
        return Card.objects.for_merchant(get_request_merchant(self.request))

    def perform_update(self, serializer: BaseSerializer) -> None:
        card = serializer.save()
        _enqueue_google_sync(card)


# ── Locations ─────────────────────────────────────────────────────────────────
class LocationListCreateView(generics.ListCreateAPIView):
    """GET /locations · POST /locations."""

    serializer_class = LocationSerializer
    permission_classes = [IsAdminOrAbove]

    def get_queryset(self) -> QuerySet[Location]:
        return Location.objects.for_merchant(get_request_merchant(self.request)).order_by(
            "-created_at"
        )

    def perform_create(self, serializer: BaseSerializer) -> None:
        serializer.save(merchant=get_request_merchant(self.request))


# ── Staff ─────────────────────────────────────────────────────────────────────
class StaffListCreateView(generics.ListCreateAPIView):
    """GET /staff (Admin+) · POST /staff (Owner — it grants access)."""

    def get_serializer_class(self) -> type:
        return StaffCreateSerializer if self.request.method == "POST" else StaffSerializer

    def get_permissions(self) -> list[BasePermission]:
        # Creating staff escalates access, so gate it behind Owner.
        if self.request.method == "POST":
            return [IsOwner()]
        return [IsAdminOrAbove()]

    def get_queryset(self) -> QuerySet[StaffUser]:
        merchant = get_request_merchant(self.request)
        return (
            StaffUser.objects.for_merchant(merchant)
            .select_related("user", "location")
            .order_by("-created_at")
        )


# ── Customers ─────────────────────────────────────────────────────────────────
class CustomerListView(generics.ListAPIView):
    """GET /customers — CustomerCard list, filterable by card / status / phone."""

    serializer_class = CustomerSerializer
    permission_classes = [IsAdminOrAbove]

    def get_queryset(self) -> QuerySet[CustomerCard]:
        qs = (
            CustomerCard.objects.for_merchant(get_request_merchant(self.request))
            .select_related("card")
            .order_by("-created_at")
        )
        # Filter param names (card / status / phone) are NOT pinned by the
        # contract (§3.6 only says "filterable"). Confirmed to match Momen's
        # expectation; rename here if the frontend uses different keys.
        params = self.request.query_params
        if card_id := params.get("card"):
            qs = qs.filter(card_id=card_id)
        if status_ := params.get("status"):
            qs = qs.filter(status=status_)
        if phone := params.get("phone"):
            qs = qs.filter(customer_phone__icontains=phone)
        return qs


# ── Analytics ─────────────────────────────────────────────────────────────────
class AnalyticsSummaryView(APIView):
    """GET /analytics/summary — headline metrics for the merchant (contract §3.6)."""

    permission_classes = [IsAdminOrAbove]

    @extend_schema(responses=AnalyticsSummarySerializer)
    def get(self, request: Request) -> Response:
        merchant = get_request_merchant(request)
        customers = CustomerCard.objects.for_merchant(merchant)

        enrollments = customers.count()
        active_cards = customers.filter(status=CustomerCardStatus.ACTIVE).count()
        redemptions = Redemption.objects.for_merchant(merchant).count()

        wallet_regs = WalletRegistration.objects.filter(
            customer_card__merchant=merchant, is_active=True
        )
        apple_count = wallet_regs.filter(platform=WalletPlatform.APPLE).count()
        google_count = wallet_regs.filter(platform=WalletPlatform.GOOGLE).count()

        # Returning customers: >= 2 STAMP events on the card.
        returning = (
            customers.annotate(
                stamp_events=Count(
                    "ledger_entries",
                    filter=Q(ledger_entries__event_type=LedgerEvent.STAMP),
                )
            )
            .filter(stamp_events__gte=2)
            .count()
        )
        repeat_rate = round(returning / enrollments, 4) if enrollments else 0.0

        payload: dict[str, Any] = {
            "enrollments": enrollments,
            "active_cards": active_cards,
            "redemptions": redemptions,
            "apple_count": apple_count,
            "google_count": google_count,
            "repeat_rate": repeat_rate,
        }
        return Response(AnalyticsSummarySerializer(payload).data)
