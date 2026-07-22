"""API key status — configured, working, and what it has cost.

Secrets are **not** stored here or anywhere in the database. Every credential
lives in the environment alongside Paymob's and WhatsApp's, which is the pattern
this codebase already follows and the safer one: a key in Postgres is readable
by anyone with database access, ships in every nightly backup, and travels
through replication.

So this module reports *about* keys without ever handling one. The spec's four
columns are all derivable:

* Status      — is the variable set, and did the last call succeed
* Last used   — the newest ApiUsage row for that provider
* Usage       — counted from the ledger, per day and per month
* Test        — an actual round-trip, which is the only honest definition

A key is never echoed back, not even masked. A masked key still leaks length
and prefix, and nobody needs to read it from a web page to know it works — the
test button answers the real question.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from leadgen import enums
from leadgen.models import ApiUsage

_ZERO = Decimal("0")

# Which env var backs each provider, and whether the module can run without it.
PROVIDERS: dict[str, dict] = {
    enums.ApiProvider.GOOGLE_PLACES: {
        "setting": "GOOGLE_PLACES_API_KEY",
        "required": True,
        "purpose": "Business discovery. Nothing runs without it.",
    },
    enums.ApiProvider.GOOGLE_GEOCODING: {
        "setting": "GOOGLE_GEOCODING_API_KEY",
        "required": True,
        "purpose": "Turns a job's address into a search centre. Falls back to the Places key.",
    },
    enums.ApiProvider.GLM: {
        "setting": "GLM_API_KEY",
        "required": False,
        "purpose": (
            "AI enrichment. Needs a pay-as-you-go key — a GLM Coding Plan "
            "subscription is licensed for coding tools, not application traffic."
        ),
    },
    enums.ApiProvider.TWILIO_LOOKUP: {
        "setting": "TWILIO_AUTH_TOKEN",
        "required": False,
        "purpose": (
            "Confirms a phone is reachable and what kind of line it is. "
            "Without it, numbers are validated offline and capped at “possible”."
        ),
    },
    enums.ApiProvider.HUNTER: {
        "setting": "HUNTER_API_KEY",
        "required": False,
        "purpose": (
            "Email deliverability. Without it, addresses are checked for syntax, "
            "disposability and a resolving domain only."
        ),
    },
}


def _configured(provider: str) -> bool:
    return bool(getattr(settings, PROVIDERS[provider]["setting"], ""))


def status_all() -> list[dict]:
    """One row per provider for the API Keys screen."""
    now = timezone.now()
    day_start = now - timedelta(days=1)
    month_start = now - timedelta(days=30)
    labels = dict(enums.ApiProvider.choices)

    rows = []
    for provider, meta in PROVIDERS.items():
        usage = ApiUsage.objects.filter(provider=provider)
        latest = usage.order_by("-created_at").first()
        configured = _configured(provider)

        rows.append(
            {
                "provider": provider,
                "label": labels[provider],
                "purpose": meta["purpose"],
                "required": meta["required"],
                "env_var": meta["setting"],
                "configured": configured,
                # Three states, not two: a key can be set and still broken, and
                # the difference is what the operator is trying to find out.
                "state": _state(configured, latest, meta["required"]),
                "last_used_at": latest.created_at if latest else None,
                "last_call_succeeded": latest.succeeded if latest else None,
                "calls_24h": _calls(usage.filter(created_at__gte=day_start)),
                "calls_30d": _calls(usage.filter(created_at__gte=month_start)),
                "cost_24h_usd": _cost(usage.filter(created_at__gte=day_start)),
                "cost_30d_usd": _cost(usage.filter(created_at__gte=month_start)),
            }
        )
    return rows


def _state(configured: bool, latest, required: bool) -> str:
    if not configured:
        return "missing" if required else "not_configured"
    if latest is None:
        return "untested"
    return "ok" if latest.succeeded else "failing"


def _calls(queryset) -> int:
    return queryset.aggregate(n=Coalesce(Sum("calls"), 0))["n"]


def _cost(queryset) -> Decimal:
    return queryset.aggregate(
        total=Coalesce(Sum("cost_usd"), _ZERO, output_field=DecimalField())
    )["total"]


def test_connection(provider: str) -> tuple[bool, str]:
    """Make a real call and report what happened.

    A live round-trip, not a "is the variable non-empty" check. Those are
    different questions and only one of them is worth a button: a key can be
    present, malformed, expired, IP-restricted or out of quota, and every one of
    those looks identical to a configuration check.
    """
    if provider not in PROVIDERS:
        return False, f"Unknown provider “{provider}”."
    if not _configured(provider):
        return False, f"{PROVIDERS[provider]['setting']} is not set."

    if provider == enums.ApiProvider.GLM:
        from leadgen.glm import GlmClient

        return GlmClient().ping()

    if provider in (enums.ApiProvider.GOOGLE_PLACES, enums.ApiProvider.GOOGLE_GEOCODING):
        return _test_google(provider)

    if provider == enums.ApiProvider.TWILIO_LOOKUP:
        return _test_twilio()

    if provider == enums.ApiProvider.HUNTER:
        return _test_hunter()

    return False, "No test available for this provider."


def _test_google(provider: str) -> tuple[bool, str]:
    from leadgen.places import PlacesClient, PlacesError

    client = PlacesClient()
    try:
        if provider == enums.ApiProvider.GOOGLE_GEOCODING:
            located = client.geocode("Cairo, Egypt", region="eg")
            return (
                (True, f"Geocoded Cairo to {located[0]:.4f}, {located[1]:.4f}")
                if located
                else (False, "Geocoding returned no result for a known city.")
            )
        # One minimal Text Search. It is a billed call, which is the honest
        # cost of proving the key works.
        page = client.search_text(
            text_query="cafe in Cairo",
            lat=30.0444,
            lng=31.2357,
            radius_m=1000,
            region_code="EG",
        )
        return True, f"Places returned {len(page.results)} results"
    except PlacesError as exc:
        return False, str(exc)


def _test_twilio() -> tuple[bool, str]:
    import httpx

    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(
                "https://lookups.twilio.com/v2/PhoneNumbers/+201001234567",
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            )
    except httpx.HTTPError as exc:
        return False, f"Could not reach Twilio: {exc}"

    if response.status_code in (200, 404):
        # 404 means "no such number", which still proves the credentials work.
        return True, "Twilio Lookup accepted the credentials"
    if response.status_code in (401, 403):
        return False, "Twilio rejected the credentials."
    return False, f"Twilio returned HTTP {response.status_code}"


def _test_hunter() -> tuple[bool, str]:
    import httpx

    try:
        with httpx.Client(timeout=20) as client:
            response = client.get(
                "https://api.hunter.io/v2/account",
                params={"api_key": settings.HUNTER_API_KEY},
            )
    except httpx.HTTPError as exc:
        return False, f"Could not reach Hunter: {exc}"

    if response.status_code != 200:
        return False, f"Hunter returned HTTP {response.status_code}"

    data = (response.json() or {}).get("data") or {}
    used = (data.get("requests") or {}).get("searches", {}).get("used")
    available = (data.get("requests") or {}).get("searches", {}).get("available")
    if used is not None and available is not None:
        return True, f"Hunter OK — {used}/{available} searches used this period"
    return True, "Hunter accepted the key"
