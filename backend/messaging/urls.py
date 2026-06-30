"""Messaging / Engage URLs (contract §3.6). Mounted at /api/v1/ (no prefix)."""

from django.urls import path

from messaging.views import (
    AutomationDetailView,
    AutomationListView,
    CampaignListCreateView,
    CustomerMessageView,
    SegmentListView,
)

urlpatterns = [
    path("campaigns", CampaignListCreateView.as_view(), name="campaign-list"),
    path("segments", SegmentListView.as_view(), name="segment-list"),
    path("automations", AutomationListView.as_view(), name="automation-list"),
    path("automations/<str:key>", AutomationDetailView.as_view(), name="automation-detail"),
    path(
        "customers/<uuid:customer_id>/message",
        CustomerMessageView.as_view(),
        name="customer-message",
    ),
]
