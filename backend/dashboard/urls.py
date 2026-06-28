"""Dashboard URLs (contract §3.6). Mounted at /api/v1/ (no extra prefix)."""

from django.urls import path

from dashboard.views import (
    AnalyticsSummaryView,
    CardDetailView,
    CardListCreateView,
    CustomerListView,
    LocationListCreateView,
    StaffListCreateView,
)

urlpatterns = [
    path("cards", CardListCreateView.as_view(), name="card-list"),
    path("cards/<uuid:card_id>", CardDetailView.as_view(), name="card-detail"),
    path("customers", CustomerListView.as_view(), name="customer-list"),
    path("staff", StaffListCreateView.as_view(), name="staff-list"),
    path("locations", LocationListCreateView.as_view(), name="location-list"),
    path("analytics/summary", AnalyticsSummaryView.as_view(), name="analytics-summary"),
]
