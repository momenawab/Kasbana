"""API tests for the Phase 2 surfaces: queues, cost tracking and API keys.

The security property under test is that **no endpoint ever returns a
credential**. Keys live in the environment; this API reports on them.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser
from leadgen import enums
from leadgen.models import AiEnrichment, ApiUsage, GeneratedLead, SearchJob, Verification

pytestmark = pytest.mark.django_db

AI_QUEUE = "/api/admin/v1/leadgen/queues/ai"
VERIFY_QUEUE = "/api/admin/v1/leadgen/queues/verification"
COSTS = "/api/admin/v1/leadgen/costs"
KEYS = "/api/admin/v1/leadgen/api-keys"

SECRET = "sk-super-secret-value-9876543210"


def admin_of(role: str, email: str) -> AdminUser:
    admin = AdminUser(email=email, name=email.split("@")[0], role=role)
    admin.set_password("supersecret1")
    admin.save()
    return admin


@pytest.fixture
def sales():
    return admin_of(AdminRole.SALES, "sales@stampn.net")


@pytest.fixture
def read_only():
    return admin_of(AdminRole.READ_ONLY, "ro@stampn.net")


@pytest.fixture
def superadmin():
    return admin_of(AdminRole.SUPER_ADMIN, "super@stampn.net")


def client_for(admin: AdminUser) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return client


def make_lead() -> GeneratedLead:
    job = SearchJob.objects.create(country="EG", city="Cairo", business_types=["cafe"])
    return GeneratedLead.objects.create(
        job=job, place_id="p1", business_name="Karam Cafe", business_status="OPERATIONAL"
    )


class TestQueues:
    def test_ai_queue_lists_with_stats(self, sales):
        lead = make_lead()
        AiEnrichment.objects.create(lead=lead, status=enums.TaskStatus.COMPLETED)

        response = client_for(sales).get(AI_QUEUE)
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["stats"]["completed"] == 1
        assert response.data["stats"]["failed"] == 0

    def test_stats_describe_the_whole_queue_not_the_filter(self, sales):
        """They are the header an operator reads to decide what to filter to."""
        lead = make_lead()
        AiEnrichment.objects.create(lead=lead, status=enums.TaskStatus.FAILED)

        response = client_for(sales).get(f"{AI_QUEUE}?status=completed")
        assert len(response.data["results"]) == 0
        assert response.data["stats"]["failed"] == 1

    def test_queue_row_omits_the_raw_payload(self, sales):
        """Large, only useful when debugging one answer, and the queue renders
        hundreds of rows."""
        lead = make_lead()
        AiEnrichment.objects.create(lead=lead, raw_response={"huge": "x" * 5000})

        row = client_for(sales).get(AI_QUEUE).data["results"][0]
        assert "raw_response" not in row
        assert row["business_name"] == "Karam Cafe"

    def test_verification_queue(self, sales):
        lead = make_lead()
        Verification.objects.create(
            lead=lead,
            kind=enums.VerificationKind.PHONE,
            target="+201001234567",
            status=enums.TaskStatus.COMPLETED,
            result=enums.VerificationResult.VERIFIED,
        )
        response = client_for(sales).get(VERIFY_QUEUE)
        assert response.data["results"][0]["result"] == "verified"

    def test_read_only_may_watch_the_queues(self, read_only):
        assert client_for(read_only).get(AI_QUEUE).status_code == 200


class TestRunStage:
    def test_read_only_cannot_spend_money(self, read_only):
        job = SearchJob.objects.create(country="EG", city="Cairo", business_types=["cafe"])
        response = client_for(read_only).post(
            f"/api/admin/v1/leadgen/jobs/{job.id}/run/ai", {}, format="json"
        )
        assert response.status_code == 403

    def test_sales_can_run_enrichment(self, sales):
        job = SearchJob.objects.create(country="EG", city="Cairo", business_types=["cafe"])
        with patch("leadgen.views.tasks.enqueue_stage", return_value="queued") as spawn:
            response = client_for(sales).post(
                f"/api/admin/v1/leadgen/jobs/{job.id}/run/ai", {}, format="json"
            )
        assert response.status_code == 200
        assert spawn.called

    def test_unknown_stage_is_a_400(self, sales):
        job = SearchJob.objects.create(country="EG", city="Cairo", business_types=["cafe"])
        response = client_for(sales).post(
            f"/api/admin/v1/leadgen/jobs/{job.id}/run/telepathy", {}, format="json"
        )
        assert response.status_code == 400

    def test_running_a_stage_is_audited(self, sales):
        job = SearchJob.objects.create(country="EG", city="Cairo", business_types=["cafe"])
        with patch("leadgen.views.tasks.enqueue_stage", return_value="queued"):
            client_for(sales).post(f"/api/admin/v1/leadgen/jobs/{job.id}/run/ai", {}, format="json")
        assert AdminAuditLog.objects.filter(action="leadgen.stage.ai").exists()

    def test_the_run_route_is_not_swallowed_by_the_action_route(self, sales):
        """`/jobs/<id>/run/ai` must not resolve as the action named "run"."""
        from django.urls import resolve

        job_id = "11111111-1111-1111-1111-111111111111"
        assert (
            resolve(f"/api/admin/v1/leadgen/jobs/{job_id}/run/ai").func.view_class.__name__
            == "RunStageView"
        )


class TestCosts:
    def test_summary_is_read_from_the_ledger(self, sales):
        lead = make_lead()
        ApiUsage.objects.create(
            provider=enums.ApiProvider.GLM,
            operation="chat.completions",
            job=lead.job,
            lead=lead,
            calls=1,
            tokens_in=1000,
            tokens_out=400,
            cost_usd=Decimal("0.001480"),
        )

        data = client_for(sales).get(COSTS).data
        assert Decimal(data["total_cost_usd"]) == Decimal("0.001480")
        assert data["total_calls"] == 1
        assert data["by_provider"][0]["provider"] == "glm"

    def test_cost_per_lead_excludes_merged_duplicates(self, sales):
        """Duplicates were absorbed into a survivor; counting them would
        understate what a callable lead actually cost."""
        lead = make_lead()
        GeneratedLead.objects.create(
            job=lead.job, place_id="p2", business_name="Karam Maadi", duplicate_of=lead
        )
        ApiUsage.objects.create(
            provider=enums.ApiProvider.GOOGLE_PLACES,
            operation="places.searchText",
            job=lead.job,
            calls=1,
            cost_usd=Decimal("0.032"),
        )

        data = client_for(sales).get(COSTS).data
        assert data["leads"] == 1
        assert Decimal(data["cost_per_lead_usd"]) == Decimal("0.032")

    def test_summary_declares_that_rates_are_estimates(self, sales):
        assert client_for(sales).get(COSTS).data["rates_are_estimates"] is True

    def test_empty_ledger_does_not_divide_by_zero(self, sales):
        data = client_for(sales).get(COSTS).data
        assert Decimal(data["total_cost_usd"]) == 0
        assert data["cost_per_imported_usd"] is None


class TestApiKeys:
    def test_status_never_returns_a_key(self, sales, settings):
        """The property that matters most here."""
        settings.GLM_API_KEY = SECRET

        response = client_for(sales).get(KEYS)
        assert response.status_code == 200
        assert SECRET not in response.content.decode()

    def test_not_even_a_masked_form_is_returned(self, sales, settings):
        """A mask still leaks length and prefix, and nobody needs to read a key
        from a web page to learn whether it works."""
        settings.GLM_API_KEY = SECRET
        body = client_for(sales).get(KEYS).content.decode()
        assert SECRET[:8] not in body
        assert "sk-" not in body

    def test_reports_configured_state_and_the_env_var_name(self, sales, settings):
        settings.GLM_API_KEY = SECRET
        settings.HUNTER_API_KEY = ""

        providers = {p["provider"]: p for p in client_for(sales).get(KEYS).data["providers"]}
        assert providers["glm"]["configured"] is True
        assert providers["glm"]["env_var"] == "GLM_API_KEY"
        assert providers["hunter"]["configured"] is False
        assert providers["hunter"]["state"] == "not_configured"

    def test_configured_but_never_used_is_untested_not_ok(self, sales, settings):
        """Configured and working are different states, which is why the test
        button exists."""
        settings.GLM_API_KEY = SECRET
        providers = {p["provider"]: p for p in client_for(sales).get(KEYS).data["providers"]}
        assert providers["glm"]["state"] == "untested"

    def test_a_failing_last_call_shows_as_failing(self, sales, settings):
        settings.GLM_API_KEY = SECRET
        ApiUsage.objects.create(
            provider=enums.ApiProvider.GLM, operation="chat.completions", succeeded=False
        )
        providers = {p["provider"]: p for p in client_for(sales).get(KEYS).data["providers"]}
        assert providers["glm"]["state"] == "failing"

    def test_missing_required_key_is_distinguished_from_optional(self, sales, settings):
        settings.GOOGLE_PLACES_API_KEY = ""
        settings.HUNTER_API_KEY = ""
        providers = {p["provider"]: p for p in client_for(sales).get(KEYS).data["providers"]}
        assert providers["google_places"]["state"] == "missing"
        assert providers["hunter"]["state"] == "not_configured"

    def test_test_connection_is_super_admin_only(self, sales):
        """A test is a live billed call — not something every reader should be
        able to trigger repeatedly."""
        response = client_for(sales).post(f"{KEYS}/glm/test", {}, format="json")
        assert response.status_code == 403

    def test_super_admin_can_test_and_it_is_audited(self, superadmin, settings):
        settings.GLM_API_KEY = ""
        response = client_for(superadmin).post(f"{KEYS}/glm/test", {}, format="json")

        assert response.status_code == 200
        assert response.data["ok"] is False
        assert "GLM_API_KEY is not set" in response.data["message"]
        assert AdminAuditLog.objects.filter(action="leadgen.apikey.test").exists()

    def test_unknown_provider_is_reported_not_crashed(self, superadmin):
        response = client_for(superadmin).post(f"{KEYS}/nonsense/test", {}, format="json")
        assert response.status_code == 200
        assert response.data["ok"] is False
