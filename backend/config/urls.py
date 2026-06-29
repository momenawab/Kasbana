"""Root URL configuration (contract §3.6).

Base path: ``/api/v1/``. Each phase's app include line is added here up front so
the router is never touched in parallel (contract §5). Phase 1.0 wires auth and
the schema; later phases uncomment their includes.
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import TokenRefreshView

from core.auth import EmailTokenObtainPairView


def health(_request):
    """Simple health check so deploys can be verified."""
    return JsonResponse({"status": "ok", "service": "kasbana-backend"})


api_v1: list = [
    # Auth (Phase 1.0)
    path("auth/token", EmailTokenObtainPairView.as_view(), name="auth-token"),
    path("auth/refresh", TokenRefreshView.as_view(), name="auth-refresh"),
    # Account & session: signup/forgot/reset/invite, /me, settings (Phase 1.5 — You)
    path("", include("accounts.urls")),
    # Enrollment (Phase 1.1 — You)
    path("", include("enrollment.urls")),
    # Wallet web service (Phase 1.1 — You)
    path("wallet/", include("wallets.urls")),
    # Loyalty (Phase 2)
    path("loyalty/", include("loyalty.urls")),
    # Dashboard (Phase 3)
    path("", include("dashboard.urls")),
    # Billing (Phase 1.4 — You)
    # path("billing/", include("billing.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/v1/", include((api_v1, "v1"))),
    # OpenAPI schema + docs (drf-spectacular)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
