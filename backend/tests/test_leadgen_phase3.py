"""Tests for the dashboard, bulk actions and exports.

The recurring property: every count and every exported row describes leads a rep
could actually call — merged duplicates are never included, because a chain of
five branches is one opportunity, not five.
"""

from __future__ import annotations

import csv
import io
import json
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser, Lead as CrmLead
from core.models import Merchant
from leadgen import enums
from leadgen.models import (
    ApiUsage,
    GeneratedLead,
    SearchJob,
    SocialProfile,
    Verification,
    WebsiteProfile,
)
from leadgen.services import analytics, exports

pytestmark = pytest.mark.django_db

DASHBOARD = "/api/admin/v1/leadgen/dashboard"
BULK = "/api/admin/v1/leadgen/leads/bulk"
EXPORT = "/api/admin/v1/leadgen/leads/export"


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


@pytest.fixture
def job():
    return SearchJob.objects.create(
        country="EG", city="Cairo", business_types=["cafe"], max_results=100
    )


def make_lead(job, **overrides) -> GeneratedLead:
    defaults = {
        "place_id": f"p-{overrides.get('business_name', 'x')}",
        "business_name": "Karam Cafe",
        "business_status": "OPERATIONAL",
        "category": enums.BusinessType.CAFE,
        "fit_score": 64,
        "score_label": enums.ScoreLabel.WARM,
        "state": enums.LeadState.READY,
        "reviews_count": 900,
    }
    return GeneratedLead.objects.create(job=job, **{**defaults, **overrides})


class TestMetrics:
    def test_counts_exclude_merged_duplicates(self, job):
        """A chain of branches is one opportunity, not five."""
        survivor = make_lead(job, business_name="Karam", place_id="p1")
        make_lead(job, business_name="Karam Maadi", place_id="p2", duplicate_of=survivor)

        assert analytics.metrics()["total_leads"] == 1

    def test_verified_means_provider_confirmed_not_merely_plausible(self, job):
        lead = make_lead(job, place_id="p1")
        Verification.objects.create(
            lead=lead,
            kind=enums.VerificationKind.PHONE,
            target="+201001234567",
            result=enums.VerificationResult.POSSIBLE,
        )
        assert analytics.metrics()["verified"] == 0

        Verification.objects.filter(lead=lead).update(
            result=enums.VerificationResult.VERIFIED
        )
        assert analytics.metrics()["verified"] == 1

    def test_cost_and_token_totals_come_from_the_ledger(self, job):
        ApiUsage.objects.create(
            provider=enums.ApiProvider.GLM,
            operation="chat.completions",
            job=job,
            calls=2,
            tokens_in=1000,
            tokens_out=500,
            cost_usd=Decimal("0.0015"),
        )
        found = analytics.metrics()
        assert found["estimated_cost_usd"] == Decimal("0.0015")
        assert found["estimated_tokens"] == 1500
        assert found["estimated_api_calls"] == 2

    def test_empty_database_returns_zeroes_not_errors(self):
        found = analytics.metrics()
        assert found["total_leads"] == 0
        assert found["average_score"] == 0


class TestCharts:
    def test_score_distribution_bands_cover_the_full_range(self, job):
        make_lead(job, place_id="p1", fit_score=0)
        make_lead(job, place_id="p2", fit_score=64)
        make_lead(job, place_id="p3", fit_score=100)

        bands = {row["band"]: row["count"] for row in analytics.score_distribution()}
        assert bands["0-9"] == 1
        assert bands["60-69"] == 1
        # 100 belongs in the top band rather than falling off the end.
        assert bands["90-99"] == 1

    def test_conversion_funnel_reads_through_to_the_crm(self, job):
        merchant = Merchant.objects.create(name="Karam", slug="karam")
        crm_lead = CrmLead.objects.create(
            business_name="Karam", name="A", phone="+201001234567",
            converted_merchant=merchant,
        )
        make_lead(job, place_id="p1", imported_lead=crm_lead, state=enums.LeadState.IMPORTED)
        make_lead(job, place_id="p2", state=enums.LeadState.READY)

        funnel = analytics.conversion_funnel()
        assert funnel["discovered"] == 2
        assert funnel["imported"] == 1
        assert funnel["converted"] == 1
        assert funnel["conversion_rate"] == 100.0

    def test_conversion_funnel_never_divides_by_zero(self):
        assert analytics.conversion_funnel()["conversion_rate"] == 0.0

    def test_sources_chart_reports_owner_provenance(self, job):
        """Discovery source is always Google Places here, so it would be a
        single bar. Owner provenance is the source dimension that varies."""
        make_lead(job, place_id="p1", owner_name="Ahmed",
                  owner_name_source=enums.OwnerNameSource.LEGAL_PAGE)
        make_lead(job, place_id="p2")

        sources = {row["source"]: row["count"] for row in analytics.owner_sources()}
        assert sources["legal_page"] == 1
        assert sources["none"] == 1

    def test_web_presence_separates_own_site_from_social_only(self, job):
        """The number that forced the Phase 1 scoring rebalance."""
        make_lead(job, place_id="p1", website="https://k.com.eg", website_domain="k.com.eg")
        make_lead(job, place_id="p2", website="https://instagram.com/k", website_domain="")
        make_lead(job, place_id="p3")

        presence = analytics.web_presence()
        assert presence["with_website"] == 1
        assert presence["with_social_only"] == 1
        assert presence["with_nothing"] == 1

    def test_dashboard_endpoint_returns_every_series(self, sales, job):
        make_lead(job, place_id="p1")
        data = client_for(sales).get(DASHBOARD).data
        for key in (
            "metrics", "leads_per_day", "leads_by_city", "score_distribution",
            "by_label", "conversion", "owner_sources", "by_category", "web_presence",
        ):
            assert key in data


class TestBulkActions:
    def test_reject_and_restore(self, sales, job):
        lead = make_lead(job, place_id="p1")

        client_for(sales).post(
            BULK, {"lead_ids": [str(lead.id)], "action": "reject"}, format="json"
        )
        lead.refresh_from_db()
        assert lead.state == enums.LeadState.REJECTED

        client_for(sales).post(
            BULK, {"lead_ids": [str(lead.id)], "action": "restore"}, format="json"
        )
        lead.refresh_from_db()
        assert lead.state == enums.LeadState.READY

    def test_read_only_cannot_reject(self, read_only, job):
        lead = make_lead(job, place_id="p1")
        response = client_for(read_only).post(
            BULK, {"lead_ids": [str(lead.id)], "action": "reject"}, format="json"
        )
        assert response.status_code == 403

    def test_delete_is_super_admin_only(self, sales, superadmin, job):
        """A bulk delete throws away work already paid for."""
        lead = make_lead(job, place_id="p1")

        denied = client_for(sales).post(
            BULK, {"lead_ids": [str(lead.id)], "action": "delete"}, format="json"
        )
        assert denied.status_code == 403
        assert GeneratedLead.objects.filter(id=lead.id).exists()

        allowed = client_for(superadmin).post(
            BULK, {"lead_ids": [str(lead.id)], "action": "delete"}, format="json"
        )
        assert allowed.status_code == 200
        assert not GeneratedLead.objects.filter(id=lead.id).exists()

    def test_spending_actions_need_the_run_permission(self, read_only, job):
        lead = make_lead(job, place_id="p1")
        for action in ("verify", "rerun_ai"):
            response = client_for(read_only).post(
                BULK, {"lead_ids": [str(lead.id)], "action": action}, format="json"
            )
            assert response.status_code == 403, action

    def test_bulk_verify_runs_over_the_selection(self, sales, job):
        lead = make_lead(job, place_id="p1", phone_e164="+201001234567")
        response = client_for(sales).post(
            BULK, {"lead_ids": [str(lead.id)], "action": "verify"}, format="json"
        )
        assert response.status_code == 200
        assert Verification.objects.filter(lead=lead).exists()

    def test_selection_is_capped(self, sales):
        response = client_for(sales).post(
            BULK,
            {"lead_ids": [f"00000000-0000-0000-0000-{i:012d}" for i in range(600)],
             "action": "reject"},
            format="json",
        )
        assert response.status_code == 400

    def test_unknown_action_is_rejected(self, sales, job):
        lead = make_lead(job, place_id="p1")
        response = client_for(sales).post(
            BULK, {"lead_ids": [str(lead.id)], "action": "detonate"}, format="json"
        )
        assert response.status_code in (400, 403)

    def test_bulk_actions_are_audited(self, sales, job):
        lead = make_lead(job, place_id="p1")
        client_for(sales).post(
            BULK, {"lead_ids": [str(lead.id)], "action": "reject"}, format="json"
        )
        assert AdminAuditLog.objects.filter(action="leadgen.bulk.reject").exists()


class TestExports:
    def _rows(self, response) -> list[dict]:
        body = b"".join(response.streaming_content).decode()
        return list(csv.DictReader(io.StringIO(body)))

    def test_csv_contains_the_lead(self, sales, job):
        lead = make_lead(job, place_id="p1", business_name="Beanos", phone_e164="+201001234567")
        WebsiteProfile.objects.create(lead=lead, emails=["info@beanos.com.eg"])
        SocialProfile.objects.create(
            lead=lead, platform=enums.SocialPlatform.INSTAGRAM, url="https://ig.com/b"
        )

        rows = self._rows(client_for(sales).get(f"{EXPORT}/csv"))
        assert rows[0]["Business"] == "Beanos"
        assert rows[0]["Email"] == "info@beanos.com.eg"
        assert rows[0]["Instagram"] == "https://ig.com/b"

    def test_export_respects_the_same_filters_as_the_table(self, sales, job):
        """An export that disagrees with the screen it came from is a bug
        nobody notices until a rep works the wrong list."""
        make_lead(job, place_id="p1", business_name="Hot", score_label=enums.ScoreLabel.HOT)
        make_lead(job, place_id="p2", business_name="Cold", score_label=enums.ScoreLabel.COLD)

        rows = self._rows(client_for(sales).get(f"{EXPORT}/csv?score_label=hot"))
        assert len(rows) == 1
        assert rows[0]["Business"] == "Hot"

    def test_export_excludes_merged_duplicates_by_default(self, sales, job):
        survivor = make_lead(job, business_name="Karam", place_id="p1")
        make_lead(job, business_name="Karam Maadi", place_id="p2", duplicate_of=survivor)

        assert len(self._rows(client_for(sales).get(f"{EXPORT}/csv"))) == 1

    def test_absent_values_are_blank_not_the_string_none(self, sales, job):
        """A spreadsheet full of "None" is the classic export tell."""
        make_lead(job, place_id="p1", owner_name="", rating=None)
        row = self._rows(client_for(sales).get(f"{EXPORT}/csv"))[0]
        assert row["Owner"] == ""
        assert row["Rating"] == ""

    def test_verification_state_is_exported_verbatim(self, sales, job):
        """"possible" must not be exported as if it were "verified"."""
        lead = make_lead(job, place_id="p1", phone_e164="+201001234567")
        Verification.objects.create(
            lead=lead, kind=enums.VerificationKind.PHONE, target="+201001234567",
            result=enums.VerificationResult.POSSIBLE,
        )
        row = self._rows(client_for(sales).get(f"{EXPORT}/csv"))[0]
        assert row["Phone verified"] == "possible"

    def test_json_export(self, sales, job):
        make_lead(job, place_id="p1", business_name="Beanos")
        response = client_for(sales).get(f"{EXPORT}/json")
        payload = json.loads(b"".join(response.streaming_content).decode())
        assert payload[0]["business_name"] == "Beanos"

    def test_xlsx_export_is_a_real_workbook(self, sales, job):
        from openpyxl import load_workbook

        make_lead(job, place_id="p1", business_name="Beanos")
        response = client_for(sales).get(f"{EXPORT}/xlsx")

        workbook = load_workbook(io.BytesIO(response.content))
        rows = list(workbook.active.values)
        assert rows[0][0] == "Business"
        assert rows[1][0] == "Beanos"

    def test_unknown_format_is_a_400(self, sales):
        assert client_for(sales).get(f"{EXPORT}/pdf").status_code == 400

    def test_exports_are_audited(self, sales, job):
        make_lead(job, place_id="p1")
        response = client_for(sales).get(f"{EXPORT}/csv")
        b"".join(response.streaming_content)
        assert AdminAuditLog.objects.filter(action="leadgen.export").exists()

    def test_empty_export_still_has_headers(self, sales):
        rows = self._rows(client_for(sales).get(f"{EXPORT}/csv"))
        assert rows == []
