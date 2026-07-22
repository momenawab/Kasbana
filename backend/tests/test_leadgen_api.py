"""Console API tests for lead generation.

Covers the permission split (looking is free, billing and writing are not), the
filters the results table depends on, and the CRM handover — including the two
behaviours import must never lose: it goes through the CRM's own service, and
it never writes a fit score into the CRM's engagement score.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from console import crm
from console.auth import issue_admin_tokens
from console.crm_seed import ensure_seeded
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser, Lead as CrmLead, LeadActivity
from leadgen import enums
from leadgen.models import GeneratedLead, SearchJob, SocialProfile, WebsiteProfile

pytestmark = pytest.mark.django_db

JOBS = "/api/admin/v1/leadgen/jobs"
LEADS = "/api/admin/v1/leadgen/leads"


@pytest.fixture(autouse=True)
def seeded_choices():
    ensure_seeded()


@pytest.fixture(autouse=True)
def no_broker():
    """Never touch a real broker in tests, and never run a job as a side effect
    of creating one — dispatch is asserted separately."""
    with patch("leadgen.views.enqueue", return_value="queued") as mock:
        yield mock


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
def finance():
    return admin_of(AdminRole.FINANCE, "finance@stampn.net")


def client_for(admin: AdminUser) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return client


def make_job(**overrides) -> SearchJob:
    defaults = {
        "country": "EG",
        "city": "Cairo",
        "business_types": [enums.BusinessType.CAFE],
        "center_lat": 30.0,
        "center_lng": 31.0,
        "max_results": 100,
    }
    return SearchJob.objects.create(**{**defaults, **overrides})


def make_lead(job: SearchJob, **overrides) -> GeneratedLead:
    defaults = {
        "place_id": f"place-{overrides.get('business_name', 'x')}",
        "business_name": "Karam Cafe",
        "phone_e164": "+201001234567",
        "reviews_count": 900,
        "fit_score": 64,
        "score_label": enums.ScoreLabel.WARM,
        "state": enums.LeadState.READY,
        "business_status": "OPERATIONAL",
    }
    return GeneratedLead.objects.create(job=job, **{**defaults, **overrides})


VALID_JOB = {
    "country": "EG",
    "city": "Cairo",
    "street": "Maadi",
    "business_types": [enums.BusinessType.CAFE],
    "radius_km": 3,
    "max_results": 50,
}


class TestPermissions:
    """Looking is free; putting Places on the bill is not."""

    def test_read_only_can_list_jobs(self, read_only):
        make_job()
        assert client_for(read_only).get(JOBS).status_code == 200

    def test_read_only_cannot_start_a_job(self, read_only):
        assert client_for(read_only).post(JOBS, VALID_JOB, format="json").status_code == 403

    def test_finance_cannot_start_a_job(self, finance):
        """Lead generation belongs to Sales; a billing role is not a sales role."""
        assert client_for(finance).post(JOBS, VALID_JOB, format="json").status_code == 403

    def test_read_only_cannot_import_to_crm(self, read_only):
        job = make_job()
        lead = make_lead(job)
        response = client_for(read_only).post(
            f"{LEADS}/import", {"lead_ids": [str(lead.id)]}, format="json"
        )
        assert response.status_code == 403

    def test_anonymous_is_rejected(self):
        assert APIClient().get(JOBS).status_code == 401


class TestCreateJob:
    def test_sales_creates_and_queues(self, sales, no_broker):
        with patch("leadgen.services.jobs.PlacesClient") as places:
            places.return_value.geocode.return_value = (29.96, 31.25)
            response = client_for(sales).post(JOBS, VALID_JOB, format="json")

        assert response.status_code == 201
        assert response.data["status"] == enums.JobStatus.QUEUED
        assert response.data["dispatch"] == "queued"
        assert no_broker.called

    def test_creation_is_audited_because_it_costs_money(self, sales):
        with patch("leadgen.services.jobs.PlacesClient") as places:
            places.return_value.geocode.return_value = (29.96, 31.25)
            client_for(sales).post(JOBS, VALID_JOB, format="json")

        entry = AdminAuditLog.objects.get(action="leadgen.job.created")
        assert entry.actor_email == "sales@stampn.net"
        assert entry.metadata["max_results"] == 50

    def test_rejects_max_results_outside_the_allowed_set(self, sales):
        payload = {**VALID_JOB, "max_results": 999}
        response = client_for(sales).post(JOBS, payload, format="json")
        assert response.status_code == 400

    def test_rejects_unknown_business_type(self, sales):
        payload = {**VALID_JOB, "business_types": ["spaceport"]}
        assert client_for(sales).post(JOBS, payload, format="json").status_code == 400

    def test_rejects_radius_beyond_the_cap(self, sales):
        payload = {**VALID_JOB, "radius_km": 500}
        assert client_for(sales).post(JOBS, payload, format="json").status_code == 400

    def test_ungeocodable_address_returns_400_not_500(self, sales):
        with patch("leadgen.services.jobs.PlacesClient") as places:
            places.return_value.geocode.return_value = None
            response = client_for(sales).post(JOBS, VALID_JOB, format="json")

        assert response.status_code == 400
        assert "could not place" in response.data["detail"]


class TestJobActions:
    def test_cancel(self, sales):
        job = make_job(status=enums.JobStatus.RUNNING)
        response = client_for(sales).post(f"{JOBS}/{job.id}/cancel", {}, format="json")
        assert response.status_code == 200
        assert response.data["status"] == enums.JobStatus.CANCELLED

    def test_illegal_transition_is_a_400(self, sales):
        job = make_job(status=enums.JobStatus.QUEUED)
        response = client_for(sales).post(f"{JOBS}/{job.id}/pause", {}, format="json")
        assert response.status_code == 400

    def test_unknown_action_is_a_400(self, sales):
        job = make_job()
        response = client_for(sales).post(f"{JOBS}/{job.id}/explode", {}, format="json")
        assert response.status_code == 400

    def test_resume_re_queues_so_the_job_actually_moves(self, sales, no_broker):
        job = make_job(status=enums.JobStatus.PAUSED)
        client_for(sales).post(f"{JOBS}/{job.id}/resume", {}, format="json")
        assert no_broker.called

    def test_logs_endpoint_returns_the_operator_trail(self, sales):
        job = make_job()
        job.logs.create(message="Discovery started", level=enums.LogLevel.INFO)
        job.logs.create(message="One area failed", level=enums.LogLevel.WARNING)

        response = client_for(sales).get(f"{JOBS}/{job.id}/logs?level=warning")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1


class TestLeadList:
    def test_duplicates_are_hidden_by_default(self, sales):
        """A collapsed branch is not a separate prospect — showing it would make
        one chain look like five opportunities."""
        job = make_job()
        survivor = make_lead(job, business_name="Karam", place_id="p1")
        make_lead(job, business_name="Karam Maadi", place_id="p2", duplicate_of=survivor)

        response = client_for(sales).get(f"{LEADS}?job_id={job.id}")
        assert len(response.data["results"]) == 1

        response = client_for(sales).get(f"{LEADS}?job_id={job.id}&include_duplicates=true")
        assert len(response.data["results"]) == 2

    def test_filters_by_score_label_and_minimum_score(self, sales):
        job = make_job()
        make_lead(job, place_id="p1", fit_score=80, score_label=enums.ScoreLabel.HOT)
        make_lead(job, place_id="p2", fit_score=20, score_label=enums.ScoreLabel.IGNORE)

        assert len(client_for(sales).get(f"{LEADS}?score_label=hot").data["results"]) == 1
        assert len(client_for(sales).get(f"{LEADS}?min_score=50").data["results"]) == 1

    def test_presence_filters(self, sales):
        job = make_job()
        with_site = make_lead(job, place_id="p1", website_domain="karam.com.eg")
        make_lead(job, place_id="p2")
        WebsiteProfile.objects.create(lead=with_site, emails=["info@karam.com.eg"])

        assert len(client_for(sales).get(f"{LEADS}?has_website=true").data["results"]) == 1
        assert len(client_for(sales).get(f"{LEADS}?has_email=true").data["results"]) == 1

    def test_social_filter(self, sales):
        job = make_job()
        lead = make_lead(job, place_id="p1")
        SocialProfile.objects.create(
            lead=lead, platform=enums.SocialPlatform.INSTAGRAM, url="https://ig.com/k"
        )
        make_lead(job, place_id="p2")

        assert len(client_for(sales).get(f"{LEADS}?has_instagram=true").data["results"]) == 1

    def test_search_matches_name_and_domain(self, sales):
        job = make_job()
        make_lead(job, place_id="p1", business_name="Beanos", website_domain="beanos.com.eg")
        make_lead(job, place_id="p2", business_name="Cilantro")

        assert len(client_for(sales).get(f"{LEADS}?q=beanos").data["results"]) == 1

    def test_list_row_stays_narrow(self, sales):
        """The table renders hundreds of rows; crawl payloads and raw Places
        JSON belong to the detail drawer only."""
        job = make_job()
        make_lead(job, place_id="p1")
        row = client_for(sales).get(LEADS).data["results"][0]
        assert "raw_places" not in row
        assert "website_profile" not in row

    def test_detail_carries_everything(self, sales):
        job = make_job()
        lead = make_lead(job, place_id="p1", raw_places={"id": "abc"})
        data = client_for(sales).get(f"{LEADS}/{lead.id}").data
        assert data["raw_places"] == {"id": "abc"}
        assert "owner_candidates" in data
        assert "score_breakdown" in data


class TestManualOwner:
    def test_rep_can_record_an_owner_they_found_themselves(self, sales):
        """The manual path: a name learned on a call reaches the record without
        this system going and taking it from anywhere."""
        job = make_job()
        lead = make_lead(job, place_id="p1")

        response = client_for(sales).post(
            f"{LEADS}/{lead.id}/owner",
            {"name": "Ahmed Karam", "role": "Owner", "note": "Asked on first call"},
            format="json",
        )

        assert response.status_code == 200
        lead.refresh_from_db()
        assert lead.owner_name == "Ahmed Karam"
        assert lead.owner_name_source == enums.OwnerNameSource.MANUAL
        assert lead.owner_name_confidence == enums.Confidence.HIGH

    def test_read_only_cannot_write_an_owner(self, read_only):
        job = make_job()
        lead = make_lead(job, place_id="p1")
        response = client_for(read_only).post(
            f"{LEADS}/{lead.id}/owner", {"name": "Ahmed"}, format="json"
        )
        assert response.status_code == 403


class TestImport:
    def test_import_creates_a_crm_lead_through_the_crm_service(self, sales):
        """Going through crm_service is what makes an imported lead
        indistinguishable from a manually created one — same timeline, same
        last_activity, same initial score."""
        job = make_job()
        lead = make_lead(job, place_id="p1", business_name="Karam Cafe")

        response = client_for(sales).post(
            f"{LEADS}/import", {"lead_ids": [str(lead.id)]}, format="json"
        )

        assert response.status_code == 201
        crm_lead = CrmLead.objects.get(business_name="Karam Cafe")
        assert crm_lead.source == crm.LeadSource.GOOGLE_MAPS
        # The timeline entry crm_service writes on creation.
        assert LeadActivity.objects.filter(lead=crm_lead).exists()

    def test_fit_score_never_lands_in_the_crm_engagement_score(self, sales):
        """lead_score means "how hard has a rep worked this" and is recomputed
        from the timeline. Writing a fit score there would be wrong and would be
        overwritten by the first activity anyway."""
        job = make_job()
        lead = make_lead(job, place_id="p1", fit_score=95)

        client_for(sales).post(f"{LEADS}/import", {"lead_ids": [str(lead.id)]}, format="json")

        crm_lead = CrmLead.objects.get()
        assert crm_lead.lead_score != 95
        # It travels in the opening note instead, where it stays true.
        note = LeadActivity.objects.filter(lead=crm_lead).order_by("-created_at").first()
        assert "95/100" in note.description

    def test_missing_owner_queues_a_call_rather_than_guessing_a_name(self, sales):
        """The common outcome in this market. An empty name plus a queued call
        beats greeting a shop as though it were a person."""
        job = make_job()
        lead = make_lead(job, place_id="p1", owner_name="")

        client_for(sales).post(f"{LEADS}/import", {"lead_ids": [str(lead.id)]}, format="json")

        crm_lead = CrmLead.objects.get()
        assert crm_lead.name == ""
        assert crm_lead.next_action == crm.NextAction.CALL_TOMORROW

    def test_crm_match_blocks_until_confirmed(self, sales):
        existing = CrmLead.objects.create(
            business_name="Karam Cafe", name="Ahmed", phone="+201001234567"
        )
        job = make_job()
        lead = make_lead(job, place_id="p1", crm_match=existing, crm_match_reason="phone")

        blocked = client_for(sales).post(
            f"{LEADS}/import", {"lead_ids": [str(lead.id)]}, format="json"
        )
        assert blocked.status_code == 409
        assert "already looks like" in blocked.data["skipped"][0]["reason"]

        forced = client_for(sales).post(
            f"{LEADS}/import", {"lead_ids": [str(lead.id)], "force": True}, format="json"
        )
        assert forced.status_code == 201

    def test_bulk_import_reports_per_lead_failures(self, sales):
        """Forty-nine good leads must not be refused because one is a duplicate."""
        job = make_job()
        good = make_lead(job, place_id="p1", business_name="Fresh Cafe")
        existing = CrmLead.objects.create(
            business_name="Karam", name="A", phone="+201009999999"
        )
        blocked = make_lead(
            job, place_id="p2", business_name="Karam", crm_match=existing,
            crm_match_reason="phone",
        )

        response = client_for(sales).post(
            f"{LEADS}/import", {"lead_ids": [str(good.id), str(blocked.id)]}, format="json"
        )

        assert response.status_code == 201
        assert response.data["imported"] == 1
        assert len(response.data["skipped"]) == 1

    def test_importing_twice_is_refused(self, sales):
        job = make_job()
        lead = make_lead(job, place_id="p1")
        payload = {"lead_ids": [str(lead.id)]}

        client_for(sales).post(f"{LEADS}/import", payload, format="json")
        second = client_for(sales).post(f"{LEADS}/import", payload, format="json")

        assert second.status_code == 409
        assert CrmLead.objects.count() == 1

    def test_import_updates_the_job_counter(self, sales):
        job = make_job()
        lead = make_lead(job, place_id="p1")
        client_for(sales).post(f"{LEADS}/import", {"lead_ids": [str(lead.id)]}, format="json")

        job.refresh_from_db()
        assert job.imported_count == 1
        lead.refresh_from_db()
        assert lead.state == enums.LeadState.IMPORTED

    def test_import_is_audited(self, sales):
        job = make_job()
        lead = make_lead(job, place_id="p1")
        client_for(sales).post(f"{LEADS}/import", {"lead_ids": [str(lead.id)]}, format="json")

        assert AdminAuditLog.objects.filter(action="leadgen.import").exists()
