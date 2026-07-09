"""Root URL configuration (contract §3.6).

Base path: ``/api/v1/``. Each phase's app include line is added here up front so
the router is never touched in parallel (contract §5). Phase 1.0 wires auth and
the schema; later phases uncomment their includes.
"""

from django.conf import settings
from django.conf.urls.static import static
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
    return JsonResponse({"status": "ok", "service": "stampn-backend"})


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
    # Registration-page theme + QR styling (finalize Phase 1)
    path("", include("branding.urls")),
    # Billing (Phase 1.7 — You)
    path("", include("billing.urls")),
    # Messaging / Engage (Phase 1.7 — You)
    path("", include("messaging.urls")),
    # Public marketing "Get started" lead intake (unauthenticated).
    path("", include("console.public_urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/v1/", include((api_v1, "v1"))),
    # Platform admin console — separate auth boundary (console app).
    path("api/admin/v1/", include(("console.urls", "console"), namespace="console")),
    # OpenAPI schema + docs (drf-spectacular)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
