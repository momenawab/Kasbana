"""Admin console URL routes — mounted at ``/api/admin/v1/`` (see config.urls)."""

from __future__ import annotations

from django.urls import path

from console.views import AdminLoginView, AdminMeView, AdminRefreshView
from console.views_merchants import MerchantDetailView, MerchantListView
from console.views_plans import PlanDetailView, PlanListView

urlpatterns = [
    path("auth/login", AdminLoginView.as_view(), name="admin-login"),
    path("auth/refresh", AdminRefreshView.as_view(), name="admin-refresh"),
    path("me", AdminMeView.as_view(), name="admin-me"),
    # Merchant directory (Phase 2)
    path("merchants", MerchantListView.as_view(), name="admin-merchants"),
    path(
        "merchants/<uuid:merchant_id>", MerchantDetailView.as_view(), name="admin-merchant-detail"
    ),
    # Plan catalogue (Phase 3)
    path("plans", PlanListView.as_view(), name="admin-plans"),
    path("plans/<str:key>", PlanDetailView.as_view(), name="admin-plan-detail"),
]
