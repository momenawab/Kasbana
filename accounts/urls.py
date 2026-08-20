"""Account-lifecycle URLs (Phase 1.5). Mounted at /api/v1/ (no extra prefix)."""

from django.urls import path

from accounts.views import (
    AccountExportView,
    ForgotView,
    InviteView,
    MeView,
    PasswordChangeView,
    ResetView,
    SettingsAccountView,
    SettingsBusinessView,
    SignupView,
)

urlpatterns = [
    path("auth/signup", SignupView.as_view(), name="auth-signup"),
    path("auth/forgot", ForgotView.as_view(), name="auth-forgot"),
    path("auth/reset", ResetView.as_view(), name="auth-reset"),
    path("auth/invite/<str:t>", InviteView.as_view(), name="auth-invite"),
    path("me", MeView.as_view(), name="me"),
    path("settings/business", SettingsBusinessView.as_view(), name="settings-business"),
    path("settings/account", SettingsAccountView.as_view(), name="settings-account"),
    path(
        "settings/account/password",
        PasswordChangeView.as_view(),
        name="settings-account-password",
    ),
    path("settings/account/export", AccountExportView.as_view(), name="settings-account-export"),
]
