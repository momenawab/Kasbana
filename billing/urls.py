"""Billing URLs (contract §3.6). Mounted at /api/v1/ (no extra prefix), so the
paths below are the exact contract paths with no trailing slash."""

from django.urls import path

from billing.views import (
    BillingStateView,
    CancelView,
    InvoiceListView,
    PaymobSubscriptionWebhookView,
    PaymobWebhookView,
    PlanCatalogueView,
    SubscribeView,
)

urlpatterns = [
    path("billing", BillingStateView.as_view(), name="billing-state"),
    path("billing/plans", PlanCatalogueView.as_view(), name="billing-plans"),
    path("billing/subscribe", SubscribeView.as_view(), name="billing-subscribe"),
    path("billing/invoices", InvoiceListView.as_view(), name="billing-invoices"),
    path("billing/cancel", CancelView.as_view(), name="billing-cancel"),
    path("billing/webhook/paymob", PaymobWebhookView.as_view(), name="billing-webhook-paymob"),
    # Must match SUBSCRIPTION_WEBHOOK_PATH in the create_paymob_plans command —
    # it is baked into each Paymob plan at creation time, so changing this path
    # orphans every existing plan's webhook.
    path(
        "billing/webhook/paymob/subscription",
        PaymobSubscriptionWebhookView.as_view(),
        name="billing-webhook-paymob-subscription",
    ),
]
