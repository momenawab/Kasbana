"""Billing URLs (contract §3.6). Mounted at /api/v1/ (no extra prefix), so the
paths below are the exact contract paths with no trailing slash."""

from django.urls import path

from billing.views import (
    BillingStateView,
    CancelView,
    InvoiceListView,
    PaymobWebhookView,
    SubscribeView,
)

urlpatterns = [
    path("billing", BillingStateView.as_view(), name="billing-state"),
    path("billing/subscribe", SubscribeView.as_view(), name="billing-subscribe"),
    path("billing/invoices", InvoiceListView.as_view(), name="billing-invoices"),
    path("billing/cancel", CancelView.as_view(), name="billing-cancel"),
    path("billing/webhook/paymob", PaymobWebhookView.as_view(), name="billing-webhook-paymob"),
]
