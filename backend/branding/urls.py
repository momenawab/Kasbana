"""Branding URLs (Phase 1 · finalize-phases). Mounted at /api/v1/."""

from django.urls import path

from branding.views import CardEnrollThemeView, MerchantEnrollThemeView

urlpatterns = [
    path("settings/enroll-theme", MerchantEnrollThemeView.as_view(), name="enroll-theme"),
    path(
        "cards/<uuid:card_id>/enroll-theme",
        CardEnrollThemeView.as_view(),
        name="card-enroll-theme",
    ),
]
