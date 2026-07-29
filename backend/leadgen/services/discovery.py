"""Discovery — turning one job into many Places queries, and their results
into ``GeneratedLead`` rows.

The problem this solves: Google returns at most 60 results for any single Text
Search query (20 per page, 3 pages). A job asking for 1,000 businesses therefore
cannot be one query, or ten — it has to fan out.

Fan-out is **adaptive rather than fixed**. A fixed grid wastes calls on empty
desert and still truncates a dense high street; instead each (business type,
area) query runs, and only the areas that come back *saturated* — a full 60
results, meaning Google had more to give — are split into quadrants and
re-queried. Sparse areas cost one call; dense ones get the resolution they
need. Since every call is billed, spending them where the businesses actually
are is the whole game.

Overlap between sub-cells is expected and harmless: the same cafe returned by
two cells is caught by ``place_id`` uniqueness within the job.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from leadgen import dedupe, enums
from leadgen.models import GeneratedLead, SearchJob
from leadgen.places import PlaceResult, PlacesClient, build_query

logger = logging.getLogger(__name__)

# A query returning this many results had more to give — Google truncated it.
SATURATION_THRESHOLD = 60

# How many times one cell may be quartered. Depth 3 turns one cell into up to
# 64, which at 60 results each is far past any job's ceiling; the cap exists so
# a pathologically dense city centre cannot spend an unbounded number of calls.
MAX_SPLIT_DEPTH = 3

# Splitting below this is pointless: sub-cells start returning the same
# businesses and every extra call is spent re-discovering what we have.
MIN_CELL_RADIUS_M = 250.0

_METERS_PER_DEGREE_LAT = 111_320.0


@dataclass(frozen=True)
class Cell:
    """A circular search area."""

    lat: float
    lng: float
    radius_m: float
    depth: int = 0

    def quarter(self) -> list[Cell]:
        """Four overlapping sub-cells covering this one.

        Offsets are half the radius on each axis, and each child keeps a radius
        of ``r/√2`` rather than ``r/2``. Four circles of r/2 at those offsets
        leave uncovered gaps between them — businesses in the gaps would vanish
        from the job with nothing to indicate they were missed. Sizing the
        children so their union genuinely covers the parent trades some
        duplicate results (free — dedupe absorbs them) for not silently losing
        leads.
        """
        offset = self.radius_m / 2
        child_radius = self.radius_m / math.sqrt(2)

        lat_delta = offset / _METERS_PER_DEGREE_LAT
        lng_scale = max(math.cos(math.radians(self.lat)), 0.01)
        lng_delta = offset / (_METERS_PER_DEGREE_LAT * lng_scale)

        return [
            Cell(self.lat + dy, self.lng + dx, child_radius, self.depth + 1)
            for dy in (lat_delta, -lat_delta)
            for dx in (lng_delta, -lng_delta)
        ]

    @property
    def splittable(self) -> bool:
        return self.depth < MAX_SPLIT_DEPTH and self.radius_m / math.sqrt(2) >= MIN_CELL_RADIUS_M


@dataclass
class DiscoveryOutcome:
    """What discovery did, beyond how many leads it made.

    ``ok_queries`` vs ``failed_queries`` is the distinction that matters to the
    caller: zero leads from queries that all *succeeded* is a legitimately empty
    area, while zero leads because every query *failed* is a broken job — a bad
    key, a rate limit — that must surface as a failure rather than a tidy
    "complete, 0 found". Without this the two are indistinguishable.
    """

    created: int = 0
    ok_queries: int = 0
    failed_queries: int = 0

    @property
    def all_queries_failed(self) -> bool:
        return self.ok_queries == 0 and self.failed_queries > 0


def discover(job: SearchJob, client: PlacesClient | None = None) -> DiscoveryOutcome:
    """Run discovery for ``job``, creating leads as they are found.

    Rows are written as each query returns rather than at the end, so a running
    job's results are browsable immediately and a job cancelled halfway keeps
    what it found.
    """
    client = client or PlacesClient()
    root = Cell(job.center_lat, job.center_lng, float(job.radius_km) * 1000)

    outcome = DiscoveryOutcome()
    for business_type in job.business_types:
        if outcome.created >= job.max_results:
            break
        _discover_type(job, client, business_type, root, job.max_results - outcome.created, outcome)

    return outcome


def _discover_type(
    job: SearchJob,
    client: PlacesClient,
    business_type: str,
    root: Cell,
    budget: int,
    outcome: DiscoveryOutcome,
) -> None:
    """Discover one business type, splitting saturated areas.

    Records per-query success/failure on ``outcome`` so the caller can tell a
    genuinely empty search from one where every call errored.
    """
    from leadgen.services import jobs as job_service  # circular at module level

    pending: list[Cell] = [root]
    created = 0

    while pending and created < budget:
        cell = pending.pop(0)
        query = build_query(business_type, job.city, job.street, job.province)

        try:
            results = client.search_all_pages(
                text_query=query,
                lat=cell.lat,
                lng=cell.lng,
                radius_m=int(cell.radius_m),
                included_type=_places_type(business_type),
                region_code=job.country,
                language_code="en",
            )
        except Exception as exc:  # noqa: BLE001 — one cell must not kill the job
            outcome.failed_queries += 1
            logger.warning(
                "leadgen.discovery.cell_failed",
                extra={"job": str(job.id), "type": business_type, "error": str(exc)},
            )
            job_service.log(
                job,
                f"{business_type}: search failed for one area — {exc}",
                stage=enums.PipelineStage.DISCOVERY,
                level=enums.LogLevel.WARNING,
            )
            continue

        outcome.ok_queries += 1
        made = _persist(job, results, business_type, budget - created)
        created += made
        outcome.created += made

        # Saturated: Google had more than it would return, so look closer.
        if len(results) >= SATURATION_THRESHOLD and cell.splittable:
            pending.extend(cell.quarter())
            job_service.log(
                job,
                f"{business_type}: dense area split into 4 (depth {cell.depth + 1})",
                stage=enums.PipelineStage.DISCOVERY,
            )


def _places_type(business_type: str) -> str:
    from leadgen.places import PLACES_TYPES

    return PLACES_TYPES.get(business_type, "")


def _persist(job: SearchJob, results: list[PlaceResult], business_type: str, budget: int) -> int:
    """Write results as leads, skipping any already on this job. Returns count."""
    created = 0

    for place in results:
        if created >= budget:
            break
        if not place.place_id or not place.name:
            continue

        website_domain = dedupe.registrable_domain(place.website)
        lead = GeneratedLead(
            job=job,
            place_id=place.place_id,
            business_name=place.name,
            normalized_name=dedupe.normalize_name(place.name),
            address=place.address,
            lat=place.lat,
            lng=place.lng,
            phone=place.phone,
            phone_e164=dedupe.normalize_phone(place.phone, job.country),
            website=place.website,
            # Only a domain the business actually owns may key the dedupe or be
            # crawled. An Instagram URL in the website field is a social
            # profile, and the crawl stage records it as one.
            website_domain=website_domain if dedupe.is_own_domain(website_domain) else "",
            rating=place.rating,
            reviews_count=place.reviews_count,
            photos_count=place.photos_count,
            business_status=place.business_status,
            category=business_type,
            opening_hours=place.opening_hours,
            google_maps_url=place.google_maps_url,
            raw_places=place.raw,
        )

        try:
            # Savepoint per row: a duplicate place_id is an expected outcome of
            # overlapping cells, and without this the IntegrityError would poison
            # the surrounding transaction and lose the whole page of results.
            with transaction.atomic():
                lead.save()
        except IntegrityError:
            continue  # already discovered by another cell or business type

        created += 1

    return created
