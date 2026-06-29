"""Dashboard & analytics endpoints (contract §3.6 · Phase 1.6).

Merchant configuration (cards, staff, locations), the customer list, analytics,
and the new completeness endpoints: card stats/QR, uploads, customer detail /
delete / timeline, timeseries / retention / by-location / activity feed, and
location/staff mutations.

Every queryset is scoped to the caller's merchant via ``for_merchant`` /
``get_request_merchant`` so one merchant can never read or mutate another's rows.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db.models import Count, F, Prefetch, Q, QuerySet
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from billing import entitlements
from common.errors import Conflict, PayloadTooLarge, UnprocessableEntity
from common.permissions import IsAdminOrAbove, IsOwner
from core.enums import CustomerCardStatus, LedgerEvent, Role, WalletPlatform
from core.models import (
    Card,
    CustomerCard,
    Location,
    Redemption,
    StaffUser,
    StampLedger,
    WalletRegistration,
)
from core.tenancy import get_request_merchant, get_scoped
from dashboard import analytics
from dashboard.serializers import (
    ActivityResponseSerializer,
    AnalyticsSummarySerializer,
    ByLocationResponseSerializer,
    CardQRSerializer,
    CardSerializer,
    CardStatsSerializer,
    CustomerSerializer,
    LocationSerializer,
    LocationStatsSerializer,
    RetentionResponseSerializer,
    StaffCreateSerializer,
    StaffInviteSerializer,
    StaffSerializer,
    StaffWriteSerializer,
    TimelineEventSerializer,
    TimeseriesResponseSerializer,
    UploadRequestSerializer,
    UploadSerializer,
)


def _enqueue_google_sync(card: Card) -> None:
    """Re-provision the Google LoyaltyClass after a Card create/edit."""
    from wallets.tasks import sync_google_class

    sync_google_class.delay(str(card.id))


def _card_queryset(merchant: Any) -> QuerySet[Card]:
    """Tenant-scoped Card queryset with Phase 1.6 aggregates annotated."""
    return (
        Card.objects.for_merchant(merchant)
        .annotate(
            holders=Count("customer_cards", distinct=True),
            stamps_issued=Count(
                "customer_cards__ledger_entries",
                filter=Q(customer_cards__ledger_entries__event_type=LedgerEvent.STAMP),
                distinct=True,
            ),
            rewards_redeemed=Count("rewards__redemptions", distinct=True),
        )
        .order_by("-created_at")
    )


# ── Cards ─────────────────────────────────────────────────────────────────────
class CardListCreateView(generics.ListCreateAPIView):
    """GET /cards (list) · POST /cards (create)."""

    serializer_class = CardSerializer
    permission_classes = [IsAdminOrAbove]

    def get_queryset(self) -> QuerySet[Card]:
        return _card_queryset(get_request_merchant(self.request))

    def perform_create(self, serializer: BaseSerializer) -> None:
        merchant = get_request_merchant(self.request)
        entitlements.enforce(merchant, "max_cards")
        card = serializer.save(merchant=merchant)
        _enqueue_google_sync(card)


class CardDetailView(generics.RetrieveUpdateAPIView):
    """GET /cards/{id} · PATCH /cards/{id}."""

    serializer_class = CardSerializer
    permission_classes = [IsAdminOrAbove]
    http_method_names = ["get", "patch"]
    lookup_url_kwarg = "card_id"

    def get_queryset(self) -> QuerySet[Card]:
        return _card_queryset(get_request_merchant(self.request))

    def perform_update(self, serializer: BaseSerializer) -> None:
        card = serializer.save()
        _enqueue_google_sync(card)


class CardStatsView(APIView):
    """GET /cards/{id}/stats — per-card performance stats."""

    permission_classes = [IsAdminOrAbove]

    @extend_schema(responses=CardStatsSerializer)
    def get(self, request: Request, card_id: str) -> Response:
        card = get_scoped(Card, request, pk=card_id)

        holders = card.customer_cards.count()
        stamps_issued = StampLedger.objects.filter(
            customer_card__card=card, event_type=LedgerEvent.STAMP
        ).count()
        rewards_redeemed = Redemption.objects.filter(reward__card=card).count()
        # Completion rate = share of holders who redeemed at least once (0..1).
        # Count distinct customers, not redemptions, so a repeat redeemer can't
        # push the rate above 100%.
        completed_holders = (
            Redemption.objects.filter(reward__card=card)
            .values("customer_card_id")
            .distinct()
            .count()
        )
        completion_rate = round(completed_holders / holders, 4) if holders else 0.0

        wallet_regs = WalletRegistration.objects.filter(customer_card__card=card, is_active=True)
        apple_count = wallet_regs.filter(platform=WalletPlatform.APPLE).count()
        google_count = wallet_regs.filter(platform=WalletPlatform.GOOGLE).count()

        payload = {
            "holders": holders,
            "stamps_issued": stamps_issued,
            "rewards_redeemed": rewards_redeemed,
            "completion_rate": completion_rate,
            "apple_count": apple_count,
            "google_count": google_count,
        }
        return Response(CardStatsSerializer(payload).data)


class CardQRView(APIView):
    """GET /cards/{id}/qr — enrollment QR assets for a card."""

    permission_classes = [IsAdminOrAbove]
    serializer_class = CardQRSerializer

    @extend_schema(responses=CardQRSerializer)
    def get(self, request: Request, card_id: str) -> Response:
        from enrollment.tokens import get_or_issue_enrollment_token

        card = get_scoped(Card, request, pk=card_id)
        # Reuse the card's active token so the join URL is stable across views.
        token = get_or_issue_enrollment_token(card)
        join_url = f"{settings.BASE_URL}/api/v1/enroll/{token.token}"

        try:
            import qrcode
            from qrcode.image.svg import SvgImage

            qr = qrcode.QRCode(box_size=6, border=2)
            qr.add_data(join_url)
            qr.make(fit=True)
            svg = qr.make_image(image_factory=SvgImage).to_string().decode("utf-8")
        except Exception:  # pragma: no cover - QR library unavailable
            svg = ""

        return Response({"join_url": join_url, "qr_svg": svg, "poster_pdf_url": ""})


# ── Uploads ───────────────────────────────────────────────────────────────────
_UPLOAD_TYPE_MAP: dict[str, frozenset[str]] = {
    "image/jpeg": frozenset({".jpg", ".jpeg"}),
    "image/png": frozenset({".png"}),
    "image/webp": frozenset({".webp"}),
    # SVG intentionally excluded (stored-XSS risk) — see settings.UPLOAD_ALLOWED_TYPES.
}
_UPLOAD_ALLOWED_EXTENSIONS = frozenset().union(*_UPLOAD_TYPE_MAP.values())


class UploadView(APIView):
    """POST /uploads — store a logo/image and return its URL."""

    permission_classes = [IsAdminOrAbove]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = UploadSerializer

    @extend_schema(request=UploadRequestSerializer, responses=UploadSerializer)
    def post(self, request: Request) -> Response:
        from django.core.files.storage import default_storage

        file_obj = request.FILES.get("file")
        if file_obj is None:
            raise UnprocessableEntity("No file provided.")

        if file_obj.size > settings.UPLOAD_MAX_SIZE_BYTES:
            raise PayloadTooLarge()

        ext = Path(file_obj.name).suffix.lower()
        allowed_exts = _UPLOAD_ALLOWED_EXTENSIONS
        allowed_types = settings.UPLOAD_ALLOWED_TYPES
        if ext not in allowed_exts or file_obj.content_type not in allowed_types:
            raise UnprocessableEntity("Unsupported file type.")
        if ext not in _UPLOAD_TYPE_MAP.get(file_obj.content_type, set()):
            raise UnprocessableEntity("File extension does not match content type.")

        safe_name = re.sub(r"[^\w.\-]", "_", Path(file_obj.name).name)
        path = default_storage.save(f"uploads/{timezone.now().timestamp()}_{safe_name}", file_obj)
        url = request.build_absolute_uri(settings.MEDIA_URL + path)
        return Response({"url": url}, status=status.HTTP_201_CREATED)


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
        merchant = get_request_merchant(self.request)
        entitlements.enforce(merchant, "max_locations")
        serializer.save(merchant=merchant)


class LocationDetailView(generics.RetrieveUpdateAPIView):
    """GET /locations/{id} · PATCH /locations/{id}."""

    serializer_class = LocationSerializer
    permission_classes = [IsAdminOrAbove]
    http_method_names = ["get", "patch"]
    lookup_url_kwarg = "location_id"

    def get_queryset(self) -> QuerySet[Location]:
        return Location.objects.for_merchant(get_request_merchant(self.request))


class LocationStatsView(APIView):
    """GET /locations/{id}/stats."""

    permission_classes = [IsAdminOrAbove]

    @extend_schema(responses=LocationStatsSerializer)
    def get(self, request: Request, location_id: str) -> Response:
        merchant = get_request_merchant(request)
        location = get_scoped(Location, request, pk=location_id)

        stamps = (
            StampLedger.objects.for_merchant(merchant)
            .filter(location=location, event_type=LedgerEvent.STAMP)
            .count()
        )
        redemptions = Redemption.objects.for_merchant(merchant).filter(location=location).count()
        customers = (
            CustomerCard.objects.for_merchant(merchant)
            .filter(ledger_entries__location=location)
            .distinct()
            .count()
        )

        return Response({"stamps": stamps, "redemptions": redemptions, "customers": customers})


# ── Staff ─────────────────────────────────────────────────────────────────────
class StaffListCreateView(generics.ListCreateAPIView):
    """GET /staff (Admin+) · POST /staff (Owner — it grants access)."""

    def get_serializer_class(self) -> type:
        return StaffCreateSerializer if self.request.method == "POST" else StaffSerializer

    def get_permissions(self) -> list[BasePermission]:
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

    def perform_create(self, serializer: BaseSerializer) -> None:
        entitlements.enforce(get_request_merchant(self.request), "max_staff")
        serializer.save()


class StaffInviteView(generics.CreateAPIView):
    """POST /staff/invite — create a pending StaffInvite."""

    serializer_class = StaffInviteSerializer
    permission_classes = [IsOwner]

    def perform_create(self, serializer: BaseSerializer) -> None:
        merchant = get_request_merchant(self.request)
        entitlements.enforce(merchant, "max_staff")
        serializer.save(merchant=merchant)


class StaffDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /staff/{id} — read or update role/location/active."""

    permission_classes = [IsOwner]
    http_method_names = ["get", "patch"]
    lookup_url_kwarg = "staff_id"

    def get_serializer_class(self) -> type:
        return StaffSerializer if self.request.method == "GET" else StaffWriteSerializer

    def get_queryset(self) -> QuerySet[StaffUser]:
        return StaffUser.objects.for_merchant(get_request_merchant(self.request))

    def perform_update(self, serializer: BaseSerializer) -> None:
        merchant = get_request_merchant(self.request)
        instance = self.get_object()

        new_role = serializer.validated_data.get("role", instance.role)
        new_active = serializer.validated_data.get("is_active", instance.is_active)

        if instance.role == Role.OWNER and (new_role != Role.OWNER or new_active is False):
            owners = StaffUser.objects.for_merchant(merchant).filter(role=Role.OWNER).count()
            if owners <= 1:
                raise Conflict("Cannot demote or deactivate the last owner.")

        serializer.save()


# ── Customers ─────────────────────────────────────────────────────────────────
class CustomerListView(generics.ListAPIView):
    """GET /customers — CustomerCard list, filterable."""

    serializer_class = CustomerSerializer
    permission_classes = [IsAdminOrAbove]

    def get_queryset(self) -> QuerySet[CustomerCard]:
        merchant = get_request_merchant(self.request)
        qs = (
            CustomerCard.objects.for_merchant(merchant)
            .select_related("card")
            # Prefetch only the active registrations so the serializer reads them
            # from cache (no per-row query). Filtering the related manager in the
            # serializer would bypass a plain prefetch and re-query (N+1).
            .prefetch_related(
                Prefetch(
                    "wallet_registrations",
                    queryset=WalletRegistration.objects.filter(is_active=True),
                    to_attr="active_wallet_regs",
                )
            )
            .order_by("-created_at")
        )

        params = self.request.query_params
        if card_id := params.get("card"):
            qs = qs.filter(card_id=card_id)
        if status_ := params.get("status"):
            qs = qs.filter(status=status_)
        if phone := params.get("phone"):
            qs = qs.filter(customer_phone__icontains=phone)
        if location_id := params.get("location"):
            qs = qs.filter(
                Q(ledger_entries__location_id=location_id) | Q(redemptions__location_id=location_id)
            ).distinct()
        if search := params.get("search"):
            qs = qs.filter(Q(customer_name__icontains=search) | Q(customer_phone__icontains=search))
        if segment := params.get("segment"):
            today = timezone.localdate()
            if segment == "lapsed":
                cutoff = today - timedelta(days=30)
                qs = qs.filter(Q(last_event_at__isnull=True) | Q(last_event_at__date__lt=cutoff))
            elif segment == "reward_ready":
                qs = qs.filter(stamp_count__gte=F("card__stamps_required"))

        return qs


class CustomerDetailView(generics.RetrieveDestroyAPIView):
    """GET /customers/{id} · DELETE /customers/{id} — PDPL delete."""

    serializer_class = CustomerSerializer
    permission_classes = [IsAdminOrAbove]
    lookup_url_kwarg = "customer_id"

    def get_queryset(self) -> QuerySet[CustomerCard]:
        return CustomerCard.objects.for_merchant(get_request_merchant(self.request))

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        customer = self.get_object()
        customer.delete()
        return Response({"ok": True})


class CustomerTimelineView(APIView):
    """GET /customers/{id}/timeline."""

    permission_classes = [IsAdminOrAbove]

    @extend_schema(responses=TimelineEventSerializer(many=True))
    def get(self, request: Request, customer_id: str) -> Response:
        customer = get_scoped(CustomerCard, request, pk=customer_id)

        ledger_rows = list(
            StampLedger.objects.filter(customer_card=customer)
            .select_related("staff__user", "location")
            .order_by("-created_at")
        )

        results: list[dict[str, Any]] = []
        for row in ledger_rows:
            event_type = {
                LedgerEvent.ENROLL: "enroll",
                LedgerEvent.STAMP: "stamp",
                LedgerEvent.REDEEM: "redeem",
                LedgerEvent.ADJUST: "stamp",
            }.get(row.event_type, "stamp")
            results.append(
                {
                    "event_type": event_type,
                    "delta": row.delta,
                    "balance_after": row.balance_after,
                    "staff_name": (
                        row.staff.user.get_full_name() or row.staff.user.email
                        if row.staff
                        else None
                    ),
                    "location": row.location.name if row.location else None,
                    "gps": None,
                    "at": row.created_at,
                }
            )

        results.sort(key=lambda x: x["at"], reverse=True)
        for item in results:
            item["at"] = item["at"].isoformat()
        return Response({"results": TimelineEventSerializer(results, many=True).data})


# ── Analytics ─────────────────────────────────────────────────────────────────
class AnalyticsSummaryView(APIView):
    """GET /analytics/summary — headline metrics for the merchant."""

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


def _parse_date_param(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(
            {"date": ["Invalid date format. Use ISO 8601 (YYYY-MM-DD)."]}
        ) from exc


class AnalyticsTimeseriesView(APIView):
    """GET /analytics/timeseries?from&to&metric=&location=."""

    permission_classes = [IsAdminOrAbove]
    serializer_class = TimeseriesResponseSerializer

    @extend_schema(responses=TimeseriesResponseSerializer)
    def get(self, request: Request) -> Response:
        merchant = get_request_merchant(request)
        metric = request.query_params.get("metric", "")
        from_date = _parse_date_param(request.query_params.get("from"))
        to_date = _parse_date_param(request.query_params.get("to"))
        location_id = request.query_params.get("location")

        if metric not in {"joins", "stamps", "redemptions"}:
            raise ValidationError({"metric": ["metric is required."]})

        points = analytics.timeseries(merchant, metric, from_date, to_date, location_id)
        return Response({"points": points})


class AnalyticsRetentionView(APIView):
    """GET /analytics/retention?from&to."""

    permission_classes = [IsAdminOrAbove]
    serializer_class = RetentionResponseSerializer

    @extend_schema(responses=RetentionResponseSerializer)
    def get(self, request: Request) -> Response:
        merchant = get_request_merchant(request)
        from_date = _parse_date_param(request.query_params.get("from"))
        to_date = _parse_date_param(request.query_params.get("to"))
        return Response(analytics.retention(merchant, from_date, to_date))


class AnalyticsByLocationView(APIView):
    """GET /analytics/by_location?from&to."""

    permission_classes = [IsAdminOrAbove]
    serializer_class = ByLocationResponseSerializer

    @extend_schema(responses=ByLocationResponseSerializer)
    def get(self, request: Request) -> Response:
        merchant = get_request_merchant(request)
        from_date = _parse_date_param(request.query_params.get("from"))
        to_date = _parse_date_param(request.query_params.get("to"))
        return Response({"results": analytics.by_location(merchant, from_date, to_date)})


class ActivityFeedView(APIView):
    """GET /activity?limit=."""

    permission_classes = [IsAdminOrAbove]
    serializer_class = ActivityResponseSerializer

    @extend_schema(responses=ActivityResponseSerializer)
    def get(self, request: Request) -> Response:
        merchant = get_request_merchant(request)
        try:
            limit = min(int(request.query_params.get("limit", 20)), 100)
        except (TypeError, ValueError):
            limit = 20
        return Response({"results": analytics.activity_feed(merchant, limit)})
