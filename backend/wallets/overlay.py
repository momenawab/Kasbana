"""Admin-authored pass JSON overlays — merged over the generated payload.

The pass builders (``wallets.apple.passdata`` / ``wallets.google.builders``)
compute a complete payload from the card + its template. An **overlay** is a
partial JSON document, authored by a platform admin in the Wallet Studio, that
is merged on top of that payload as the very last step. It is the escape hatch
to every pass feature the template registry does not expose — Apple
``locations`` / ``relevantDate`` / ``semantics`` / ``suppressStripShine`` /
``expirationDate``, per-field ``textAlignment`` and ``attributedValue``, Google
``imageModulesData``, and so on.

Three rules make this safe:

1. **Merge, never replace.** The generated payload keeps every smart default
   (contact back-fields, powered-by, the message field) unless the overlay
   explicitly names a key. Semantics are RFC 7386 JSON Merge Patch: nested
   objects merge recursively, arrays replace wholesale, and a ``null`` value
   *deletes* the generated key — which is how an admin removes a default they
   don't want.

2. **Identity keys are locked.** ``serialNumber``, ``authenticationToken``,
   ``webServiceURL``, ``barcodes`` and friends decide whether a pass can update
   over APNs and whether its QR resolves at the scanner. An overlay that sets
   them is rejected at save time by the serializer *and* stripped here at render
   time — belt and braces, because a row can also be written from the Django
   shell or predate the validation.

3. **Values are templated, not literal.** An overlay renders once per customer,
   so ``"{remaining}"`` resolves per person via :func:`wallets.design.
   field_context`. An admin who types a bare ``3`` freezes every customer at 3.
"""

from __future__ import annotations

from typing import Any

from wallets import templates as templates_mod

# ── Locked keys ───────────────────────────────────────────────────────────────
# Top-level keys an overlay may never set. All of these are either pass identity
# (a wrong value collides two customers or two merchants), the update channel
# (a wrong value silently stops passes refreshing), the scan payload (a wrong
# value breaks the till), or derived from card state (``voided``/``state`` come
# from CustomerCardStatus and must not be contradicted).

LOCKED_APPLE = frozenset(
    {
        "formatVersion",
        "passTypeIdentifier",
        "teamIdentifier",
        "serialNumber",
        "authenticationToken",
        "webServiceURL",
        "barcode",
        "barcodes",
        "voided",
    }
)

LOCKED_GOOGLE_CLASS = frozenset({"id"})

LOCKED_GOOGLE_OBJECT = frozenset({"id", "classId", "state", "accountId", "barcode"})

# The two halves a Google overlay may carry — Google splits one pass across a
# LoyaltyClass (per Card) and a LoyaltyObject (per CustomerCard), so the overlay
# has to say which it is patching.
GOOGLE_SECTIONS = {"class": LOCKED_GOOGLE_CLASS, "object": LOCKED_GOOGLE_OBJECT}

# An overlay is hand-authored, so a runaway document is a mistake rather than an
# attack — but it still ends up inside every signed .pkpass, and Apple caps a
# pass bundle well below this. Refuse early with a clear message.
MAX_OVERLAY_BYTES = 32_000
MAX_OVERLAY_DEPTH = 12


def locked_violations(overlay: Any, locked: frozenset[str]) -> list[str]:
    """Locked top-level keys present in ``overlay``, sorted for stable errors."""
    if not isinstance(overlay, dict):
        return []
    return sorted(k for k in overlay if k in locked)


def strip_locked(overlay: dict[str, Any], locked: frozenset[str]) -> dict[str, Any]:
    """``overlay`` without any locked key (render-time safety net)."""
    return {k: v for k, v in overlay.items() if k not in locked}


def interpolate_deep(value: Any, ctx: dict[str, Any]) -> Any:
    """Resolve ``{token}`` placeholders in every string, at any depth.

    Reuses :func:`wallets.templates.interpolate`, so the tokens an overlay may
    use are exactly the ones template labels already use ({balance}, {stamps},
    {points}, {goal}, {remaining}, {reward}, {merchant}, {program}) and an
    unknown token leaves the string untouched rather than raising. Dict *keys*
    are never interpolated — they are pass field names, not content.
    """
    if isinstance(value, str):
        return templates_mod.interpolate(value, ctx)
    if isinstance(value, dict):
        return {k: interpolate_deep(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [interpolate_deep(v, ctx) for v in value]
    return value


def merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """RFC 7386 JSON Merge Patch of ``patch`` onto ``base`` (returns a new dict).

    Objects merge recursively; a ``null`` deletes the key; everything else —
    including lists — replaces outright. Lists replacing wholesale is deliberate:
    when an admin writes ``secondaryFields`` they mean "these are the secondary
    fields", and index-wise array merging would be impossible to predict.
    """
    out = dict(base)
    for key, value in patch.items():
        if value is None:
            out.pop(key, None)
        elif isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = value
    return out


def apply(
    payload: dict[str, Any],
    overlay: Any,
    ctx: dict[str, Any] | None,
    locked: frozenset[str],
) -> dict[str, Any]:
    """Merge an admin overlay onto a generated pass payload.

    Order matters: locked keys are stripped *before* the merge (so they can never
    win), then tokens are resolved, then the result is merged. Returns ``payload``
    unchanged when the overlay is missing or not an object, so a card without an
    overlay renders exactly as it did before this module existed.
    """
    if not isinstance(overlay, dict) or not overlay:
        return payload
    cleaned = strip_locked(overlay, locked)
    if ctx is not None:
        cleaned = interpolate_deep(cleaned, ctx)
    return merge(payload, cleaned)


def apply_google(
    payload: dict[str, Any],
    overlay: Any,
    ctx: dict[str, Any] | None,
    section: str,
) -> dict[str, Any]:
    """Apply the ``class`` or ``object`` half of a Google overlay.

    A Google overlay is ``{"class": {...}, "object": {...}}`` — one column
    covering both halves of the pass, since a merchant thinks in "the card", not
    in Google's class/object split. An unknown section, or a missing half, is a
    no-op.
    """
    locked = GOOGLE_SECTIONS.get(section)
    if locked is None or not isinstance(overlay, dict):
        return payload
    return apply(payload, overlay.get(section), ctx, locked)
