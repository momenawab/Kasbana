"""Lead-generation routes, included by ``console.urls`` under ``/api/admin/v1/``.

Namespaced under ``leadgen/`` rather than merged into the console's flat route
list: this is a distinct surface with its own permissions, and keeping the
prefix means a reader can tell at a glance which endpoints spend money.
"""

from __future__ import annotations

from django.urls import path

from leadgen.views import (
    AiQueueView,
    BulkActionView,
    DashboardView,
    ExportView,
    ApiKeyStatusView,
    ApiKeyTestView,
    CostSummaryView,
    GeneratedLeadDetailView,
    GeneratedLeadImportView,
    GeneratedLeadListView,
    GeneratedLeadOwnerView,
    SearchJobActionView,
    SearchJobDetailView,
    RunStageView,
    SearchJobListView,
    SearchJobLogView,
    VerificationQueueView,
)

urlpatterns = [
    path("leadgen/jobs", SearchJobListView.as_view(), name="leadgen-jobs"),
    path("leadgen/jobs/<uuid:job_id>", SearchJobDetailView.as_view(), name="leadgen-job-detail"),
    path(
        "leadgen/jobs/<uuid:job_id>/logs",
        SearchJobLogView.as_view(),
        name="leadgen-job-logs",
    ),
    # Before the catch-all <str:action> route below, which would otherwise
    # swallow "run".
    path(
        "leadgen/jobs/<uuid:job_id>/run/<str:stage>",
        RunStageView.as_view(),
        name="leadgen-run-stage",
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
    path("leadgen/dashboard", DashboardView.as_view(), name="leadgen-dashboard"),
    path("leadgen/leads/bulk", BulkActionView.as_view(), name="leadgen-bulk"),
    path("leadgen/leads/export/<str:fmt>", ExportView.as_view(), name="leadgen-export"),
    path("leadgen/queues/ai", AiQueueView.as_view(), name="leadgen-ai-queue"),
    path(
        "leadgen/queues/verification",
        VerificationQueueView.as_view(),
        name="leadgen-verification-queue",
    ),
    path("leadgen/costs", CostSummaryView.as_view(), name="leadgen-costs"),
    path("leadgen/api-keys", ApiKeyStatusView.as_view(), name="leadgen-api-keys"),
    path(
        "leadgen/api-keys/<str:provider>/test",
        ApiKeyTestView.as_view(),
        name="leadgen-api-key-test",
    ),
]
