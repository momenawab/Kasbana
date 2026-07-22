"""Lead-generation routes, included by ``console.urls`` under ``/api/admin/v1/``.

Namespaced under ``leadgen/`` rather than merged into the console's flat route
list: this is a distinct surface with its own permissions, and keeping the
prefix means a reader can tell at a glance which endpoints spend money.
"""

from __future__ import annotations

from django.urls import path

from leadgen.views import (
    GeneratedLeadDetailView,
    GeneratedLeadImportView,
    GeneratedLeadListView,
    GeneratedLeadOwnerView,
    SearchJobActionView,
    SearchJobDetailView,
    SearchJobListView,
    SearchJobLogView,
)

urlpatterns = [
    path("leadgen/jobs", SearchJobListView.as_view(), name="leadgen-jobs"),
    path("leadgen/jobs/<uuid:job_id>", SearchJobDetailView.as_view(), name="leadgen-job-detail"),
    path(
        "leadgen/jobs/<uuid:job_id>/logs",
        SearchJobLogView.as_view(),
        name="leadgen-job-logs",
    ),
    path(
        "leadgen/jobs/<uuid:job_id>/<str:action>",
        SearchJobActionView.as_view(),
        name="leadgen-job-action",
    ),
    path("leadgen/leads", GeneratedLeadListView.as_view(), name="leadgen-leads"),
    path("leadgen/leads/import", GeneratedLeadImportView.as_view(), name="leadgen-import"),
    path(
        "leadgen/leads/<uuid:lead_id>",
        GeneratedLeadDetailView.as_view(),
        name="leadgen-lead-detail",
    ),
    path(
        "leadgen/leads/<uuid:lead_id>/owner",
        GeneratedLeadOwnerView.as_view(),
        name="leadgen-lead-owner",
    ),
]
