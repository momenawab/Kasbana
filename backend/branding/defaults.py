"""Shipped defaults for the registration theme (Phase 1 · finalize-phases).

JSONField defaults must be *callables* returning fresh dicts (a shared mutable
default would be aliased across rows), so ``fields_config`` / ``qr_style`` each
have a factory. ``phone`` is always collected (it is the loyalty key), so it is
not part of ``fields_config``.
"""

from __future__ import annotations

from typing import Any

# The optional fields a merchant may collect on the join form, with show/require
# toggles. Phone is implicit and always required.
FIELD_KEYS = ("name", "email", "birthday")

# QR module shapes the styled renderer understands (see ``branding.qr``).
QR_MODULE_STYLES = ("square", "rounded", "dots")

# Poster/QR frame templates (rendering of the frame itself lands in Phase 3 with
# the server-side poster; stored here so the merchant can pick one now).
QR_FRAMES = ("none", "scan_to_join", "collect_stamps")

TEMPLATE_KEYS = ("classic", "hero", "minimal", "bold")
FONT_KEYS = ("system", "serif", "rounded")


def default_fields_config() -> dict[str, Any]:
    return {
        "name": {"show": True, "required": False},
        "email": {"show": True, "required": False},
        "birthday": {"show": False, "required": False},
    }


def default_qr_style() -> dict[str, Any]:
    return {
        "module_style": "square",
        "fg_color": "#000000",
        "bg_color": "#FFFFFF",
        "frame": "none",
    }
