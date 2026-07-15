"""Feature-flag + platform-setting resolvers (Phase 14).

The one place runtime code asks "is this on?". Kept dependency-light so any app
can call ``flag_enabled(...)`` / ``maintenance_state()`` — callers in low-level
apps import this lazily (inside a function) so they never take a load-time
dependency on the console.

Maintenance state is read on *every* request by the middleware, so it's cached
briefly; the write path (the ops API) refreshes the cache immediately, and the
short TTL bounds staleness if the row is changed out of band.
"""

from __future__ import annotations

from typing import Any

from django.core.cache import cache

MAINTENANCE_KEY = "maintenance_mode"
_MAINTENANCE_CACHE_KEY = "ops:maintenance_state"
_MAINTENANCE_TTL = 10  # seconds

_DEFAULT_MAINTENANCE: dict[str, Any] = {"enabled": False, "message": ""}


def flag_enabled(key: str, merchant: Any | None = None) -> bool:
    """Resolve a feature flag: per-merchant override wins over the global default.

    An unknown flag resolves to ``False`` (a feature must be explicitly enabled).
    """
    from console.models import FeatureFlag, FeatureFlagOverride

    flag = FeatureFlag.objects.filter(key=key).first()
    if flag is None:
        return False
    if merchant is not None:
        override = FeatureFlagOverride.objects.filter(flag=flag, merchant=merchant).first()
        if override is not None:
            return override.enabled
    return flag.enabled


def maintenance_state(*, use_cache: bool = True) -> dict[str, Any]:
    """The current maintenance-mode state: ``{"enabled": bool, "message": str}``."""
    if use_cache:
        cached = cache.get(_MAINTENANCE_CACHE_KEY)
        if cached is not None:
            return cached
    state = _read_maintenance()
    cache.set(_MAINTENANCE_CACHE_KEY, state, _MAINTENANCE_TTL)
    return state


def _read_maintenance() -> dict[str, Any]:
    from console.models import PlatformSetting

    row = PlatformSetting.objects.filter(key=MAINTENANCE_KEY).first()
    value = row.value if row and isinstance(row.value, dict) else {}
    return {
        "enabled": bool(value.get("enabled", False)),
        "message": str(value.get("message", "")),
    }


def refresh_maintenance_cache() -> dict[str, Any]:
    """Recompute + repopulate the maintenance cache (called after a write)."""
    state = _read_maintenance()
    cache.set(_MAINTENANCE_CACHE_KEY, state, _MAINTENANCE_TTL)
    return state
