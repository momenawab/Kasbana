"""Google Maps Platform client — business discovery and geocoding.

Targets the **Places API (New)** ``places:searchText`` endpoint rather than the
legacy Places web service, for one reason that dominates every other design
choice here: the new API takes a field mask, and Google bills at the highest
SKU any requested field belongs to.

That makes the field mask a cost decision. Asking Text Search for rating,
opening hours and phone returns everything a lead needs, 20 businesses at a
time — roughly 50 billed calls for a 1,000-result job. The obvious alternative
(cheap Text Search, then a Place Details call per business to fill in the same
fields) costs ~1,050 calls at the *same* Enterprise tier, because the fields
that set the tier are the ones we need either way. Same data, an order of
magnitude apart. So Details is a fallback for gaps, never the main path.

Pagination is capped by Google at 3 pages × 20 results per query, so 60 results
is the ceiling for any single query. Larger jobs fan out across business types
and sub-areas — see ``leadgen.services.discovery``.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from django.conf import settings

from leadgen import enums
from leadgen.dedupe import haversine_meters

logger = logging.getLogger(__name__)

SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def _retry_after_seconds(response: httpx.Response) -> float:
    """Seconds to wait from a 429's ``Retry-After`` header, or 0 if absent.

    The header is either an integer number of seconds or an HTTP date. Only the
    integer form is worth honouring inside a job — a date parses to the same
    ~60s a per-minute quota needs, which is too long to hold the pipeline for.
    """
    value = response.headers.get("Retry-After", "").strip()
    if value.isdigit():
        return float(value)
    return 0.0

# Google's hard cap: 20 results per page, 3 pages per query.
PAGE_SIZE = 20
MAX_RADIUS_METERS = 50_000

# One degree of latitude, near enough, anywhere.
_METERS_PER_DEGREE_LAT = 111_320.0


def bounding_box(lat: float, lng: float, radius_m: float) -> dict[str, dict[str, float]]:
    """Smallest lat/lng rectangle containing the circle of ``radius_m``.

    ``searchText`` accepts only a rectangle in ``locationRestriction`` — circles
    belong to ``searchNearby``. A rectangle circumscribes the circle, so this
    over-selects at the corners by up to ~41%; ``search_text`` trims that back
    to the true circle with a distance check on each result.

    Using ``locationBias`` instead would avoid the arithmetic but defeat the
    purpose: a bias lets Google return businesses well outside the area, and a
    job scoped to "5km around this street" would hand reps leads they cannot
    service.
    """
    lat_delta = radius_m / _METERS_PER_DEGREE_LAT
    # Longitude degrees shrink towards the poles; guard the cosine so a job near
    # a pole cannot divide by ~0 and produce an infinite box.
    lng_scale = max(math.cos(math.radians(lat)), 0.01)
    lng_delta = radius_m / (_METERS_PER_DEGREE_LAT * lng_scale)

    return {
        "low": {
            "latitude": max(lat - lat_delta, -90.0),
            "longitude": max(lng - lng_delta, -180.0),
        },
        "high": {
            "latitude": min(lat + lat_delta, 90.0),
            "longitude": min(lng + lng_delta, 180.0),
        },
    }

# Exactly the fields a lead needs, and nothing else. Every addition here can
# move the request to a pricier SKU, so this list is reviewed as a cost change.
SEARCH_FIELD_MASK = ",".join(
    (
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.primaryType",
        "places.types",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.businessStatus",
        "places.regularOpeningHours",
        "places.googleMapsUri",
        "places.photos",
        "nextPageToken",
    )
)

# Our vocabulary → the Places type to filter on. Kept one-way and here rather
# than in ``enums`` so a Google type rename never reaches the label a rep picks.
PLACES_TYPES: dict[str, str] = {
    enums.BusinessType.CAFE: "cafe",
    enums.BusinessType.COFFEE_SHOP: "coffee_shop",
    enums.BusinessType.RESTAURANT: "restaurant",
    enums.BusinessType.BAKERY: "bakery",
    enums.BusinessType.DESSERT: "dessert_shop",
    enums.BusinessType.PIZZA: "pizza_restaurant",
    enums.BusinessType.FAST_FOOD: "fast_food_restaurant",
    enums.BusinessType.GYM: "gym",
    enums.BusinessType.SALON: "beauty_salon",
    enums.BusinessType.RETAIL: "store",
    enums.BusinessType.HOTEL: "hotel",
    enums.BusinessType.HOSPITAL: "hospital",
}


class PlacesError(RuntimeError):
    """Any failure reaching or parsing Google. Carries the operator-facing text."""


class PlacesNotConfigured(PlacesError):
    """No API key. Distinct so the job reports a setup problem, not an outage."""


@dataclass
class PlaceResult:
    """One business as Google returned it, flattened to what a lead needs.

    ``raw`` is retained verbatim: the Raw Data tab is the only way to answer
    "where did this field come from" when a mapping looks wrong, and re-running
    enrichment must never require re-paying for the call.
    """

    place_id: str
    name: str
    address: str = ""
    lat: float | None = None
    lng: float | None = None
    phone: str = ""
    website: str = ""
    rating: float | None = None
    reviews_count: int = 0
    photos_count: int = 0
    business_status: str = ""
    primary_type: str = ""
    opening_hours: dict = field(default_factory=dict)
    google_maps_url: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> PlaceResult:
        location = payload.get("location") or {}
        return cls(
            place_id=payload.get("id", ""),
            name=(payload.get("displayName") or {}).get("text", ""),
            address=payload.get("formattedAddress", ""),
            lat=location.get("latitude"),
            lng=location.get("longitude"),
            # International form first: it is already close to E.164, so
            # ``dedupe.normalize_phone`` has less to guess at.
            phone=payload.get("internationalPhoneNumber")
            or payload.get("nationalPhoneNumber", ""),
            website=payload.get("websiteUri", ""),
            rating=payload.get("rating"),
            reviews_count=payload.get("userRatingCount", 0) or 0,
            photos_count=len(payload.get("photos") or []),
            business_status=payload.get("businessStatus", ""),
            primary_type=payload.get("primaryType", ""),
            opening_hours=payload.get("regularOpeningHours") or {},
            google_maps_url=payload.get("googleMapsUri", ""),
            raw=payload,
        )


@dataclass
class SearchPage:
    results: list[PlaceResult]
    next_page_token: str = ""


class PlacesClient:
    """Thin, synchronous Google client. One instance per pipeline stage run.

    Counts its own billed calls (``billed_calls``) because cost-per-lead has to
    be measured rather than estimated — the Phase 2 cost tracker reads this
    instead of inferring spend from the number of leads produced, which would
    be wrong every time a query returned fewer results than a full page.
    """

    def __init__(self, api_key: str | None = None, timeout: float | None = None):
        self.api_key = api_key if api_key is not None else settings.GOOGLE_PLACES_API_KEY
        self.timeout = timeout or settings.LEADGEN_PLACES_TIMEOUT
        self.billed_calls = 0
        # Monotonic timestamp of the last billed call, so ``_pace`` can space the
        # next one out. Starts far in the past so the first call never waits.
        self._last_call_at = 0.0

    def _pace(self) -> None:
        """Space calls out so a job's fan-out cannot machine-gun the per-minute
        quota. Discovery fires a burst — several business types, up to three
        pages each, plus dense-area splits — and Google's per-minute limit is
        far lower than its per-day one, so without pacing a single job trips the
        minute quota and every call in the burst comes back 429. The interval is
        measured against the last call across the whole client instance, not
        per-request, so it smooths the burst rather than slowing one call.
        """
        interval = settings.LEADGEN_PLACES_MIN_INTERVAL_S
        if interval <= 0:
            return
        wait = interval - (time.monotonic() - self._last_call_at)
        if wait > 0:
            time.sleep(wait)

    def _post(self, url: str, payload: dict, field_mask: str) -> dict:
        """POST, distinguishing the three failure kinds that need three responses.

        * **4xx that we caused** (400/401/403) — the request is wrong or the key
          is; it will fail identically forever, so fail immediately with the
          reason rather than burning attempts.
        * **429 rate limit** — Google is saying "too fast", not "broken". A tight
          retry loop makes it worse and, because every attempt is a billed call,
          triple-charges the daily cap for something that cannot succeed inside a
          few seconds. So we honour ``Retry-After`` once (capped), then stop with
          a message that names the fix — raise the per-minute quota.
        * **5xx / network** — genuinely transient; the short backoff is right.
        """
        if not self.api_key:
            raise PlacesNotConfigured(
                "GOOGLE_PLACES_API_KEY is not set — add it to the environment "
                "before starting a search job."
            )

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": field_mask,
        }

        last_error = ""
        rate_limited = False
        for attempt in range(3):
            self._pace()
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as exc:  # network-level: worth retrying
                last_error = f"network error: {exc}"
                logger.warning("places.request.network_error", extra={"attempt": attempt})
                if attempt < 2:
                    time.sleep(2**attempt)  # 1s, 2s
                continue

            # Counted the moment Google answers: a 200 and a 429 both consume
            # quota, and under-counting spend is worse than over-counting it.
            self.billed_calls += 1
            self._last_call_at = time.monotonic()

            if response.status_code == 200:
                return response.json()

            if response.status_code in (400, 401, 403):
                raise PlacesError(
                    f"Google rejected the request ({response.status_code}). "
                    f"Check the API key's restrictions and enabled APIs. "
                    f"{response.text[:200]}"
                )

            if response.status_code == 429:
                # A per-minute quota resets in ~60s, which is too long to hold a
                # whole pipeline for. Wait a short Retry-After if Google gives one
                # and it is within the cap; otherwise stop now rather than spend
                # more billed calls that will only 429 again.
                rate_limited = True
                last_error = f"HTTP 429: {response.text[:200]}"
                retry_after = _retry_after_seconds(response)
                cap = settings.LEADGEN_PLACES_RETRY_AFTER_CAP_S
                if attempt < 2 and 0 < retry_after <= cap:
                    logger.warning(
                        "places.request.rate_limited",
                        extra={"retry_after": retry_after},
                    )
                    time.sleep(retry_after)
                    continue
                break  # no useful wait — stop instead of burning more calls

            # 5xx and anything else transient.
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            logger.warning("places.request.retryable", extra={"status": response.status_code})
            if attempt < 2:
                time.sleep(2**attempt)

        if rate_limited:
            raise PlacesError(
                "Google Places rate-limited this job (HTTP 429 on "
                "SearchTextRequest per minute). Raise the per-minute quota in the "
                "Google Cloud console, or lower the job's size/priority. "
                f"Detail: {last_error}"
            )
        raise PlacesError(f"Google Places unreachable after 3 attempts — {last_error}")

    def search_text(
        self,
        *,
        text_query: str,
        lat: float,
        lng: float,
        radius_m: int,
        included_type: str = "",
        region_code: str = "",
        language_code: str = "",
        page_token: str = "",
    ) -> SearchPage:
        """One page of up to 20 businesses, restricted to the job's radius.

        Google is given the bounding rectangle (the only shape ``searchText``
        restricts by); the corners it over-returns are trimmed here against the
        true circle, so the caller gets exactly the area the job asked for.
        """
        effective_radius = float(min(radius_m, MAX_RADIUS_METERS))
        payload: dict[str, Any] = {
            "textQuery": text_query,
            "pageSize": PAGE_SIZE,
            "locationRestriction": {
                "rectangle": bounding_box(lat, lng, effective_radius),
            },
        }
        if included_type:
            payload["includedType"] = included_type
        if region_code:
            payload["regionCode"] = region_code.upper()
        if language_code:
            payload["languageCode"] = language_code
        if page_token:
            payload["pageToken"] = page_token

        data = self._post(SEARCH_TEXT_URL, payload, SEARCH_FIELD_MASK)
        places = [PlaceResult.from_api(p) for p in (data.get("places") or [])]

        # Trim the rectangle's corners back to the circle. A result without
        # coordinates is kept: it is rare, and dropping a business because
        # Google omitted its location loses a real lead for a formatting reason.
        inside = [
            place
            for place in places
            if place.lat is None
            or place.lng is None
            or haversine_meters(lat, lng, place.lat, place.lng) <= effective_radius
        ]

        return SearchPage(results=inside, next_page_token=data.get("nextPageToken", ""))

    def search_all_pages(self, *, max_pages: int | None = None, **kwargs) -> list[PlaceResult]:
        """Every page for one query, up to Google's 3-page ceiling.

        A page token needs a moment to become valid on Google's side; without
        the pause the second page intermittently returns empty, which reads as
        "this area has 20 businesses" and silently truncates the job.
        """
        limit = max_pages or settings.LEADGEN_PLACES_MAX_PAGES
        collected: list[PlaceResult] = []
        token = ""

        for page in range(limit):
            if page:
                time.sleep(2)
            search_page = self.search_text(page_token=token, **kwargs)
            collected.extend(search_page.results)
            token = search_page.next_page_token
            if not token:
                break

        return collected

    def geocode(self, address: str, *, region: str = "") -> tuple[float, float] | None:
        """Centre coordinates for a job's address, or None if Google can't place it.

        Uses the classic Geocoding API — it has no new-API equivalent and is
        billed separately and cheaply (once per job, not per lead).
        """
        key = settings.GOOGLE_GEOCODING_API_KEY
        if not key:
            raise PlacesNotConfigured("GOOGLE_GEOCODING_API_KEY is not set.")

        params = {"address": address, "key": key}
        if region:
            params["region"] = region.lower()

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(GEOCODE_URL, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise PlacesError(f"Geocoding request failed: {exc}") from exc

        self.billed_calls += 1

        status = data.get("status")
        if status == "ZERO_RESULTS":
            return None
        if status != "OK":
            raise PlacesError(
                f"Geocoding failed ({status}): {data.get('error_message', 'no detail')}"
            )

        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]


def build_query(business_type: str, city: str, street: str = "", province: str = "") -> str:
    """Human-readable query text for one business type in one area.

    Text Search wants natural language even when ``includedType`` is set — the
    text narrows *where*, the type narrows *what*. Sending only a type returns
    results ranked for the whole restriction circle rather than the street.
    """
    label = enums.BusinessType(business_type).label
    where = ", ".join(part for part in (street, city, province) if part)
    return f"{label} in {where}" if where else label
