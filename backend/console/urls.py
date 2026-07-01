"""Admin console URL routes — mounted at ``/api/admin/v1/`` (see config.urls)."""

from __future__ import annotations

from django.urls import path

from console.views import AdminLoginView, AdminMeView, AdminRefreshView

urlpatterns = [
    path("auth/login", AdminLoginView.as_view(), name="admin-login"),
    path("auth/refresh", AdminRefreshView.as_view(), name="admin-refresh"),
    path("me", AdminMeView.as_view(), name="admin-me"),
]
