"""Admin console URL routes — mounted at ``/api/admin/v1/`` (see config.urls)."""

from __future__ import annotations

from django.urls import path

from console.views import AdminLoginView, AdminMeView, AdminRefreshView
from console.views_merchants import MerchantDetailView, MerchantListView
from console.views_plans import PlanDetailView, PlanListView
from console.views_subscription import (
    CompView,
    ExtendTrialView,
    LockView,
    MerchantSubscriptionView,
    SubscriptionAuditView,
    UnlockView,
)

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
    # Subscription management (Phase 4)
    path(
        "merchants/<uuid:merchant_id>/subscription",
        MerchantSubscriptionView.as_view(),
        name="admin-merchant-subscription",
    ),
    path(
        "merchants/<uuid:merchant_id>/subscription/extend-trial",
        ExtendTrialView.as_view(),
        name="admin-merchant-subscription-extend-trial",
    ),
    path(
        "merchants/<uuid:merchant_id>/subscription/comp",
        CompView.as_view(),
        name="admin-merchant-subscription-comp",
    ),
    path(
        "merchants/<uuid:merchant_id>/subscription/lock",
        LockView.as_view(),
        name="admin-merchant-subscription-lock",
    ),
    path(
        "merchants/<uuid:merchant_id>/subscription/unlock",
        UnlockView.as_view(),
        name="admin-merchant-subscription-unlock",
    ),
    path(
        "merchants/<uuid:merchant_id>/subscription/audit",
        SubscriptionAuditView.as_view(),
        name="admin-merchant-subscription-audit",
    ),
]
