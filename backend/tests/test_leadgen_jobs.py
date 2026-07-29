"""Tests for search-job lifecycle, fan-out and the enrichment pipeline.

No network: a fake Places client supplies results, and every lead used here
either has no website or a platform URL, so the crawler short-circuits before
opening a connection.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from console.models import Lead as CrmLead
from leadgen import enums
from leadgen.models import GeneratedLead, SearchJob
from leadgen.places import PlaceResult
from leadgen.services import discovery, jobs, pipeline

pytestmark = pytest.mark.django_db


class FakePlaces:
    """Stands in for ``PlacesClient``. Returns queued pages, counts its calls."""

    def __init__(self, pages: list[list[PlaceResult]] | None = None, geocode_to=(30.06, 31.22)):
        self.pages = list(pages or [])
        self.geocode_to = geocode_to
        self.billed_calls = 0
        self.queries: list[tuple[float, float, int]] = []

    def geocode(self, address, region=""):
        self.billed_calls += 1
        return self.geocode_to

    def search_all_pages(self, *, lat, lng, radius_m, **kwargs):
        self.billed_calls += 1
        self.queries.append((lat, lng, radius_m))
        return self.pages.pop(0) if self.pages else []


def place(place_id: str, name: str, **overrides) -> PlaceResult:
    defaults = {
        "address": "Maadi, Cairo",
        "lat": 29.96,
        "lng": 31.25,
        "business_status": "OPERATIONAL",
        "reviews_count": 100,
    }
    return PlaceResult(place_id=place_id, name=name, **{**defaults, **overrides})


def make_job(**overrides) -> SearchJob:
    defaults = {
        "country": "EG",
        "city": "Cairo",
        "business_types": [enums.BusinessType.CAFE],
        "max_results": 100,
    }
    return jobs.create(client=FakePlaces(), **{**defaults, **overrides})


class TestCreate:
    def test_geocodes_and_stores_the_centre(self):
        job = jobs.create(
            country="EG",
            city="Cairo",
            business_types=[enums.BusinessType.CAFE],
            client=FakePlaces(geocode_to=(30.0444, 31.2357)),
        )
        assert (job.center_lat, job.center_lng) == (30.0444, 31.2357)
        assert job.status == enums.JobStatus.QUEUED

    def test_unplaceable_address_fails_at_creation_not_at_run_time(self):
        """The operator is still looking at the form — telling them ten minutes
        later via a failed worker is a worse correction loop."""

        class NoMatch(FakePlaces):
            def geocode(self, address, region=""):
                return None

        with pytest.raises(jobs.JobError, match="could not place"):
            jobs.create(
                country="EG",
                city="Nowhere",
                business_types=[enums.BusinessType.CAFE],
                client=NoMatch(),
            )

    def test_rejects_empty_business_types(self):
        with pytest.raises(jobs.JobError, match="at least one"):
            jobs.create(country="EG", city="Cairo", business_types=[], client=FakePlaces())

    def test_rejects_unknown_business_type(self):
        with pytest.raises(jobs.JobError, match="Unknown business types"):
            jobs.create(
                country="EG", city="Cairo", business_types=["spaceport"], client=FakePlaces()
            )

    def test_rejects_max_results_outside_the_allowed_set(self):
        """A free-text maximum lets one job exhaust a day of Places quota."""
        with pytest.raises(jobs.JobError, match="Max results"):
            jobs.create(
                country="EG",
                city="Cairo",
                business_types=[enums.BusinessType.CAFE],
                max_results=999,
                client=FakePlaces(),
            )

    def test_duplicate_business_types_collapse(self):
        job = jobs.create(
            country="EG",
            city="Cairo",
            business_types=[enums.BusinessType.CAFE, enums.BusinessType.CAFE],
            client=FakePlaces(),
        )
        assert job.business_types == [enums.BusinessType.CAFE]


class TestTransitions:
    def test_pause_resume_cycle(self):
        job = make_job()
        job.status = enums.JobStatus.RUNNING
        job.save()

        jobs.pause(job)
        assert job.status == enums.JobStatus.PAUSED
        jobs.resume(job)
        assert job.status == enums.JobStatus.QUEUED

    def test_cannot_pause_a_queued_job(self):
        with pytest.raises(jobs.JobError):
            jobs.pause(make_job())

    def test_cannot_cancel_a_finished_job(self):
        job = make_job()
        job.status = enums.JobStatus.COMPLETED
        job.save()
        with pytest.raises(jobs.JobError):
            jobs.cancel(job)

    def test_retry_discards_previous_results(self):
        """A retry follows a fix; blending pre-fix and post-fix leads would
        make the results impossible to reason about."""
        job = make_job()
        GeneratedLead.objects.create(job=job, place_id="p1", business_name="Karam")
        job.status = enums.JobStatus.FAILED
        job.discovered_count = 1
        job.save()

        jobs.retry(job)
        assert job.status == enums.JobStatus.QUEUED
        assert job.leads.count() == 0
        assert job.discovered_count == 0

    def test_cannot_retry_a_running_job(self):
        job = make_job()
        job.status = enums.JobStatus.RUNNING
        job.save()
        with pytest.raises(jobs.JobError):
            jobs.retry(job)


class TestFanOut:
    def test_sparse_area_costs_one_query(self):
        job = make_job()
        client = FakePlaces([[place("p1", "Karam Cafe")]])
        discovery.discover(job, client)
        assert len(client.queries) == 1

    def test_saturated_area_is_split_into_quadrants(self):
        """60 results means Google truncated — there is more to find, so look
        closer rather than accepting the ceiling."""
        job = make_job()
        saturated = [place(f"p{i}", f"Cafe {i}") for i in range(60)]
        client = FakePlaces([saturated, [], [], [], []])

        discovery.discover(job, client)
        assert len(client.queries) == 5  # the parent, then its four children

    def test_children_cover_the_parent_area(self):
        """Children at r/2 offsets with r/2 radius leave gaps, and a business in
        a gap vanishes with nothing to show it was missed."""
        from leadgen.services.discovery import Cell

        parent = Cell(30.0, 31.0, 1000.0)
        children = parent.quarter()
        assert len(children) == 4
        # r/√2 ≈ 707m each: the union covers the parent, with overlap.
        assert all(c.radius_m > parent.radius_m / 2 for c in children)
        assert all(c.depth == 1 for c in children)

    def test_splitting_stops_at_the_depth_cap(self):
        from leadgen.services.discovery import MAX_SPLIT_DEPTH, Cell

        assert Cell(30.0, 31.0, 5000.0, depth=MAX_SPLIT_DEPTH).splittable is False

    def test_tiny_cells_are_not_split_further(self):
        from leadgen.services.discovery import Cell

        assert Cell(30.0, 31.0, 200.0).splittable is False

    def test_discovery_respects_max_results(self):
        job = make_job(max_results=25)
        client = FakePlaces([[place(f"p{i}", f"Cafe {i}") for i in range(60)]])
        discovery.discover(job, client)
        assert job.leads.count() == 25

    def test_same_place_from_two_cells_is_stored_once(self):
        """Overlapping children re-return the same businesses by design."""
        job = make_job()
        saturated = [place(f"p{i}", f"Cafe {i}") for i in range(60)]
        client = FakePlaces([saturated, [place("p1", "Cafe 1")], [], [], []])
        discovery.discover(job, client)
        assert job.leads.filter(place_id="p1").count() == 1

    def test_platform_website_is_not_stored_as_a_domain(self):
        """An Instagram URL must never key the dedupe or reach the crawler."""
        job = make_job()
        client = FakePlaces(
            [[place("p1", "1980 Coffee", website="https://www.instagram.com/1980.cof")]]
        )
        discovery.discover(job, client)
        lead = job.leads.get()
        assert lead.website  # kept for the rep to click
        assert lead.website_domain == ""  # but not usable as an identity key


class TestDeduplicate:
    def _job_with(self, *leads: dict) -> SearchJob:
        job = make_job()
        for index, fields in enumerate(leads):
            GeneratedLead.objects.create(job=job, place_id=f"p{index}", **fields)
        return job

    def test_shared_phone_collapses(self):
        job = self._job_with(
            {"business_name": "Karam", "phone_e164": "+201001234567", "reviews_count": 500},
            {"business_name": "Karam Cafe", "phone_e164": "+201001234567", "reviews_count": 10},
        )
        assert pipeline.deduplicate(job) == 1
        assert job.leads.filter(duplicate_reason=enums.DedupeReason.PHONE).count() == 1

    def test_survivor_is_the_best_documented_listing(self):
        """A chain's most-reviewed branch is the one a rep should call."""
        job = self._job_with(
            {"business_name": "Karam", "phone_e164": "+201001234567", "reviews_count": 10},
            {"business_name": "Karam", "phone_e164": "+201001234567", "reviews_count": 900},
        )
        pipeline.deduplicate(job)
        survivor = job.leads.get(duplicate_of__isnull=True)
        assert survivor.reviews_count == 900

    def test_shared_domain_collapses(self):
        job = self._job_with(
            {"business_name": "Karam Maadi", "website_domain": "karam.com.eg", "reviews_count": 50},
            {
                "business_name": "Karam Zamalek",
                "website_domain": "karam.com.eg",
                "reviews_count": 5,
            },
        )
        assert pipeline.deduplicate(job) == 1

    def test_branches_collapse_and_become_a_branch_count(self):
        """The signal the score rewards: one conversation, one head office."""
        job = make_job()
        for index, area in enumerate(("Maadi", "Zamalek", "Dokki")):
            GeneratedLead.objects.create(
                job=job,
                place_id=f"p{index}",
                business_name=f"Karam Cafe {area}",
                normalized_name="karam",
                reviews_count=100 - index,
                lat=30.0 + index,
                lng=31.0 + index,
            )
        pipeline.deduplicate(job)

        survivor = job.leads.get(duplicate_of__isnull=True)
        assert survivor.branch_count == 3
        assert job.leads.filter(duplicate_of=survivor).count() == 2

    def test_empty_normalised_name_matches_nothing(self):
        """Two all-filler names are unmatchable, not equal to each other."""
        job = self._job_with(
            {"business_name": "The Company", "normalized_name": ""},
            {"business_name": "The Group", "normalized_name": ""},
        )
        assert pipeline.deduplicate(job) == 0

    def test_distinct_businesses_survive(self):
        job = self._job_with(
            {"business_name": "Cairo Kitchen", "normalized_name": "cairo kitchen"},
            {"business_name": "Cairo Grill", "normalized_name": "cairo grill"},
        )
        assert pipeline.deduplicate(job) == 0
        assert job.leads.filter(duplicate_of__isnull=True).count() == 2


class TestCrmMatch:
    def test_matching_phone_flags_the_existing_lead(self):
        existing = CrmLead.objects.create(
            business_name="Karam Cafe", name="Ahmed", phone="+201001234567"
        )
        job = make_job()
        lead = GeneratedLead.objects.create(
            job=job, place_id="p1", business_name="Karam Cafe", phone_e164="+201001234567"
        )

        assert pipeline.match_crm(lead) is True
        lead.refresh_from_db()
        assert lead.crm_match_id == existing.id
        assert lead.state == enums.LeadState.DUPLICATE

    def test_no_match_marks_the_lead_ready(self):
        job = make_job()
        lead = GeneratedLead.objects.create(
            job=job, place_id="p1", business_name="Brand New Cafe", phone_e164="+201009999999"
        )
        assert pipeline.match_crm(lead) is False
        lead.refresh_from_db()
        assert lead.state == enums.LeadState.READY

    def test_similar_business_name_is_the_last_resort(self):
        CrmLead.objects.create(business_name="Karam Cafe", name="Ahmed", phone="+201005555555")
        job = make_job()
        lead = GeneratedLead.objects.create(
            job=job, place_id="p1", business_name="Karam Cafe", normalized_name="karam cafe"
        )
        assert pipeline.match_crm(lead) is True
        lead.refresh_from_db()
        assert lead.crm_match_reason == "business_name"


class TestRun:
    def test_full_run_reaches_completed_with_counters(self):
        job = make_job()
        client = FakePlaces(
            [
                [
                    place("p1", "Karam Cafe", reviews_count=900),
                    place("p2", "Beanos", reviews_count=40),
                ]
            ]
        )

        jobs.run(job, client=client)

        job.refresh_from_db()
        assert job.status == enums.JobStatus.COMPLETED
        assert job.discovered_count == 2
        assert job.ready_count == 2
        assert job.finished_at is not None

    def test_leads_are_scored_during_the_run(self):
        job = make_job()
        client = FakePlaces([[place("p1", "Karam Cafe", reviews_count=900, rating=4.8)]])
        jobs.run(job, client=client)

        lead = job.leads.get()
        assert lead.fit_score > 0
        assert lead.score_label
        assert lead.score_breakdown

    def test_cancelled_job_stops_and_keeps_what_it_found(self):
        job = make_job()
        client = FakePlaces([[place("p1", "Karam Cafe")]])

        # Cancel the moment discovery has written its rows.
        original = pipeline.deduplicate

        def cancel_then_dedupe(j):
            SearchJob.objects.filter(pk=j.pk).update(status=enums.JobStatus.CANCELLED)
            return original(j)

        pipeline.deduplicate = cancel_then_dedupe
        try:
            jobs.run(job, client=client)
        finally:
            pipeline.deduplicate = original

        job.refresh_from_db()
        assert job.status == enums.JobStatus.CANCELLED
        assert job.leads.count() == 1  # discovery's work survives

    def test_discovery_that_fails_every_query_fails_the_job(self):
        """The production bug: every Places call 429'd and the job reported
        "complete, 0 leads", indistinguishable from an empty area. A search that
        found nothing because everything errored is a failure, not a result."""

        class Broken(FakePlaces):
            def search_all_pages(self, **kwargs):
                raise RuntimeError("Places is down")

        job = make_job()
        jobs.run(job, client=Broken())

        job.refresh_from_db()
        assert job.status == enums.JobStatus.FAILED
        assert "failed every" in job.error
        assert job.logs.filter(level=enums.LogLevel.WARNING).exists()

    def test_one_failed_query_among_successes_still_completes(self):
        """A single bad cell must not fail a job that found real leads — the
        distinction is *all* queries failing, not *any*."""

        class Flaky(FakePlaces):
            def __init__(self):
                super().__init__([[place("p1", "Karam Cafe")]])
                self._calls = 0

            def search_all_pages(self, **kwargs):
                self._calls += 1
                if self._calls == 1:
                    return super().search_all_pages(**kwargs)
                raise RuntimeError("one flaky cell")

        job = make_job(business_types=[enums.BusinessType.CAFE, enums.BusinessType.RESTAURANT])
        jobs.run(job, client=Flaky())

        job.refresh_from_db()
        assert job.status == enums.JobStatus.COMPLETED
        assert job.leads.count() == 1

    def test_cannot_run_a_completed_job(self):
        job = make_job()
        job.status = enums.JobStatus.COMPLETED
        job.save()
        with pytest.raises(jobs.JobError):
            jobs.run(job, client=FakePlaces())

    def test_every_run_leaves_an_operator_log(self):
        job = make_job()
        jobs.run(job, client=FakePlaces([[place("p1", "Karam")]]))
        messages = [entry.message for entry in job.logs.all()]
        assert any("Discovery" in m for m in messages)
        assert any("complete" in m.lower() for m in messages)


class TestEnqueueConsumerCheck:
    """A queue nobody consumes accepts messages happily and never runs them.

    This was a live bug: the production worker consumed default/wallet/messaging
    only, so every leadgen job sat at "Queued" forever with nothing in any log
    explaining why. The publisher cannot tell a healthy queue from an
    unconsumed one — it has to ask the workers.
    """

    def _job(self) -> SearchJob:
        return make_job()

    def test_a_listening_worker_means_queued(self):
        from leadgen import tasks

        job = self._job()
        with (
            patch.object(tasks.run_search_job, "apply_async"),
            patch.object(tasks, "consumers_for", return_value=1),
        ):
            assert tasks.enqueue(job) == "queued"

        job.refresh_from_db()
        assert job.status == enums.JobStatus.QUEUED

    def test_no_consumer_fails_the_job_immediately_naming_the_queue(self):
        """Better a clear failure in seconds than a silent wait forever."""
        from leadgen import tasks

        job = self._job()
        with (
            patch.object(tasks.run_search_job, "apply_async"),
            patch.object(tasks, "consumers_for", return_value=0),
        ):
            assert tasks.enqueue(job) == "unconsumed"

        job.refresh_from_db()
        assert job.status == enums.JobStatus.FAILED
        assert "leadgen" in job.error
        assert "-Q leadgen" in job.error  # tells the operator the actual fix
        assert job.finished_at is not None

    def test_no_consumer_does_not_run_inline(self):
        """A 1,000-result sweep inside the creating request would hang the
        browser and time out the gateway."""
        from leadgen import tasks

        job = self._job()
        with (
            patch.object(tasks.run_search_job, "apply_async"),
            patch.object(tasks, "consumers_for", return_value=0),
            patch.object(tasks.job_service, "run") as ran,
        ):
            tasks.enqueue(job)

        assert not ran.called

    def test_an_unanswerable_inspect_leaves_the_job_queued(self):
        """None means "could not ask", which is not evidence of a problem —
        failing a healthy job on a flaky inspect would be worse than waiting."""
        from leadgen import tasks

        job = self._job()
        with (
            patch.object(tasks.run_search_job, "apply_async"),
            patch.object(tasks, "consumers_for", return_value=None),
        ):
            assert tasks.enqueue(job) == "queued"

        job.refresh_from_db()
        assert job.status == enums.JobStatus.QUEUED

    def test_no_broker_still_runs_inline(self):
        """The developer-machine path must survive the new check."""
        from kombu.exceptions import OperationalError

        from leadgen import tasks

        job = self._job()
        with (
            patch.object(
                tasks.run_search_job, "apply_async", side_effect=OperationalError("no broker")
            ),
            patch.object(tasks.job_service, "run") as ran,
        ):
            assert tasks.enqueue(job) == "inline"

        assert ran.called

    def test_priority_picks_the_queue_named_in_the_failure(self):
        from leadgen import tasks

        job = make_job(priority=enums.JobPriority.BACKGROUND)
        with (
            patch.object(tasks.run_search_job, "apply_async"),
            patch.object(tasks, "consumers_for", return_value=0),
        ):
            tasks.enqueue(job)

        job.refresh_from_db()
        assert "leadgen_bg" in job.error

    def test_every_priority_maps_to_a_queue_the_prod_worker_consumes(self):
        """Guards the original bug directly: the compose worker command and the
        priority map must not drift apart again."""
        import pathlib
        import re

        from leadgen import tasks

        compose = (
            pathlib.Path(__file__).resolve().parents[2] / "infra" / "compose.prod.yml"
        ).read_text()
        consumed: set[str] = set()
        for match in re.finditer(r"celery -A config worker -Q ([\w,]+)", compose):
            consumed.update(match.group(1).split(","))

        missing = set(tasks.QUEUE_FOR_PRIORITY.values()) - consumed
        assert not missing, f"no production worker consumes: {sorted(missing)}"
