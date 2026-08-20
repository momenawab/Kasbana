"""Enrollment URLs (contract §3.6). Mounted under /api/v1/."""

from django.urls import path

from enrollment.views import EnrollView

urlpatterns = [
    path("enroll/<str:token>", EnrollView.as_view(), name="enroll"),
]
