"""Admin console URL routes — mounted at ``/api/admin/v1/`` (see config.urls)."""

from __future__ import annotations

from django.urls import path

from console.views import AdminLoginView, AdminMeView, AdminRefreshView
from console.views_billing import DunningListView, DunningNotifyView, ReconciliationView
from console.views_invoices import (
    InvoiceDetailView,
    InvoiceListView,
    InvoiceRetryView,
    MerchantInvoiceCreateView,
)
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
from console.views_support import (
    ActivityView,
    ClearStuckCheckoutView,
    ImpersonateView,
    ImpersonationEndView,
    ImpersonationListView,
    ResendInviteView,
    SendPasswordResetView,
    SupportNotesView,
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
    # Billing, invoices & dunning (Phase 5)
    path("invoices", InvoiceListView.as_view(), name="admin-invoices"),
    path("invoices/<uuid:invoice_id>", InvoiceDetailView.as_view(), name="admin-invoice-detail"),
    path(
        "invoices/<uuid:invoice_id>/retry", InvoiceRetryView.as_view(), name="admin-invoice-retry"
    ),
    path(
        "merchants/<uuid:merchant_id>/invoices",
        MerchantInvoiceCreateView.as_view(),
        name="admin-merchant-invoice-create",
    ),
    path("billing/dunning", DunningListView.as_view(), name="admin-billing-dunning"),
    path(
        "merchants/<uuid:merchant_id>/dunning/notify",
        DunningNotifyView.as_view(),
        name="admin-merchant-dunning-notify",
    ),
    path(
        "billing/reconciliation", ReconciliationView.as_view(), name="admin-billing-reconciliation"
    ),
    # Support tools & impersonation (Phase 6)
    path(
        "merchants/<uuid:merchant_id>/impersonate",
        ImpersonateView.as_view(),
        name="admin-merchant-impersonate",
    ),
    path(
        "merchants/<uuid:merchant_id>/impersonations",
        ImpersonationListView.as_view(),
        name="admin-merchant-impersonations",
    ),
    path("impersonate/end", ImpersonationEndView.as_view(), name="admin-impersonate-end"),
    path(
        "merchants/<uuid:merchant_id>/support/send-password-reset",
        SendPasswordResetView.as_view(),
        name="admin-merchant-send-password-reset",
    ),
    path(
        "merchants/<uuid:merchant_id>/support/resend-invite",
        ResendInviteView.as_view(),
        name="admin-merchant-resend-invite",
    ),
    path(
        "merchants/<uuid:merchant_id>/support/clear-stuck-checkout",
        ClearStuckCheckoutView.as_view(),
        name="admin-merchant-clear-stuck-checkout",
    ),
    path(
        "merchants/<uuid:merchant_id>/support/notes",
        SupportNotesView.as_view(),
        name="admin-merchant-support-notes",
    ),
    path(
        "merchants/<uuid:merchant_id>/activity",
        ActivityView.as_view(),
        name="admin-merchant-activity",
    ),
]
