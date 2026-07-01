"""Dashboard URLs (contract §3.6). Mounted at /api/v1/ (no extra prefix)."""

from django.urls import path

from dashboard.views import (
    ActivityFeedView,
    AnalyticsByLocationView,
    AnalyticsRetentionView,
    AnalyticsSummaryView,
    AnalyticsTimeseriesView,
    CardDetailView,
    CardListCreateView,
    CardQRView,
    CardStatsView,
    CustomerDetailView,
    CustomerListView,
    CustomerTimelineView,
    LocationDetailView,
    LocationListCreateView,
    LocationStatsView,
    StaffDetailView,
    StaffInviteView,
    StaffListCreateView,
    UploadView,
)

urlpatterns = [
    # Cards
    path("cards", CardListCreateView.as_view(), name="card-list"),
    path("cards/<uuid:card_id>", CardDetailView.as_view(), name="card-detail"),
    path("cards/<uuid:card_id>/stats", CardStatsView.as_view(), name="card-stats"),
    path("cards/<uuid:card_id>/qr", CardQRView.as_view(), name="card-qr"),
    # Uploads
    path("uploads", UploadView.as_view(), name="upload"),
    # Customers
    path("customers", CustomerListView.as_view(), name="customer-list"),
    path("customers/<uuid:customer_id>", CustomerDetailView.as_view(), name="customer-detail"),
    path(
        "customers/<uuid:customer_id>/timeline",
        CustomerTimelineView.as_view(),
        name="customer-timeline",
    ),
    # Locations
    path("locations", LocationListCreateView.as_view(), name="location-list"),
    path("locations/<uuid:location_id>", LocationDetailView.as_view(), name="location-detail"),
    path("locations/<uuid:location_id>/stats", LocationStatsView.as_view(), name="location-stats"),
    # Staff
    path("staff", StaffListCreateView.as_view(), name="staff-list"),
    path("staff/invite", StaffInviteView.as_view(), name="staff-invite"),
    path("staff/<uuid:staff_id>", StaffDetailView.as_view(), name="staff-detail"),
    # Analytics
    path("analytics/summary", AnalyticsSummaryView.as_view(), name="analytics-summary"),
    path("analytics/timeseries", AnalyticsTimeseriesView.as_view(), name="analytics-timeseries"),
    path("analytics/retention", AnalyticsRetentionView.as_view(), name="analytics-retention"),
    path("analytics/by_location", AnalyticsByLocationView.as_view(), name="analytics-by-location"),
    path("activity", ActivityFeedView.as_view(), name="activity"),
]
