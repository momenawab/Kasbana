"""Lead import — bring a spreadsheet of prospects into the pipeline.

Sales buys a list, or exports one from Google Maps, and it arrives as a CSV or
an .xlsx with whatever column names the source felt like using. This turns that
into leads without anyone retyping four hundred rows.

Three things shape the design:

**Nothing is imported blind.** Parsing and importing are separate calls: the
console previews what it found, proposes a column mapping, and the human
confirms it before a single row is written. A mapping guessed wrong and applied
silently would put phone numbers in the area field of four hundred leads, and
nobody would notice until they called one.

**A bad row is skipped, not fatal.** Real spreadsheets have a blank line at row
73 and a header repeated at row 200. Aborting the whole import for one of those
is useless behaviour; the summary names what was skipped and why.

**Imported leads go through the same door as manual ones.** Each row is created
by ``crm_service.create_manual_lead``, so it gets its provenance, its timeline
entry and its score exactly like a lead typed in by hand. An import that wrote
rows straight to the table would produce leads that are subtly different from
every other lead in the system.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from django.db import transaction

from common.errors import UnprocessableEntity
from console import crm, crm_service
from console.models import AdminUser, CrmChoice, Lead

# A spreadsheet big enough to time out the request is a spreadsheet that should
# be split. The cap is on *rows parsed*, checked while streaming, so a 200k-row
# file is rejected before it is held in memory rather than after.
MAX_ROWS = 5_000

# Sample rows returned with the preview. Enough for a person to see that the
# mapping is right; few enough that the response stays small.
PREVIEW_ROWS = 5

CSV_EXTENSIONS = frozenset({".csv"})
EXCEL_EXTENSIONS = frozenset({".xlsx", ".xlsm"})


class ImportError_(Exception):
    """A file that cannot be imported, explained for a salesperson."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


# Lead fields a spreadsheet may fill, and the header names that map to each.
# Aliases are lowercase and punctuation-stripped (see ``_normalise``) so
# "Business Name", "business_name" and "BUSINESS NAME" all land on the same
# field. Only plain text fields are importable: status, priority and the rest
# are CRM state that the pipeline sets, not facts about the business.
IMPORTABLE_FIELDS: dict[str, dict[str, Any]] = {
    "business_name": {
        "label": "Business",
        "required": True,
        "aliases": ("business", "business name", "company", "name", "shop", "store", "title"),
    },
    "name": {
        "label": "Owner",
        "aliases": ("owner", "owner name", "contact", "contact name", "person", "full name"),
    },
    "phone": {
        "label": "Phone",
        "required": True,
        "aliases": ("phone", "phone number", "mobile", "telephone", "tel", "number"),
    },
    "whatsapp": {"label": "WhatsApp", "aliases": ("whatsapp", "whats app", "wa")},
    "email": {"label": "Email", "aliases": ("email", "e mail", "mail", "email address")},
    "area": {
        "label": "Area",
        "aliases": ("area", "district", "neighbourhood", "neighborhood", "zone"),
    },
    "address": {"label": "Address", "aliases": ("address", "street", "location", "full address")},
    "website": {"label": "Website", "aliases": ("website", "web", "site", "url")},
    "instagram": {"label": "Instagram", "aliases": ("instagram", "ig", "insta")},
    "facebook": {"label": "Facebook", "aliases": ("facebook", "fb")},
    "google_maps_url": {
        "label": "Google Maps",
        "aliases": ("google maps", "maps", "maps url", "google maps url", "gmaps"),
    },
    "category": {"label": "Category", "aliases": ("category", "type", "business type", "vertical")},
    "notes": {"label": "Notes", "aliases": ("notes", "note", "comment", "comments", "remarks")},
}

REQUIRED_FIELDS: tuple[str, ...] = tuple(
    f for f, spec in IMPORTABLE_FIELDS.items() if spec.get("required")
)

# Longest text a cell may contribute, per field, so one absurd cell cannot blow
# past the column width and 500 the whole import.
_MAX_LEN: dict[str, int] = {
    "business_name": 160,
    "name": 120,
    "phone": 40,
    "whatsapp": 40,
    "email": 254,
    "area": 120,
    "address": 255,
    "website": 200,
    "instagram": 120,
    "facebook": 200,
    "google_maps_url": 500,
    "category": 64,
}


def _normalise(header: str) -> str:
    """Fold a spreadsheet header to its comparable form: lowercase, no
    punctuation, single-spaced. "Business-Name " and "business name" agree."""
    cleaned = "".join(c if c.isalnum() else " " for c in str(header).lower())
    return " ".join(cleaned.split())


def suggest_mapping(columns: list[str]) -> dict[str, str]:
    """Guess which column feeds which field: ``{column: field}``.

    A guess, offered to the human, never applied on its own. Exact alias matches
    only — no fuzzy scoring. A near-match that silently loads phone numbers into
    the address field is worse than leaving the column unmapped and making
    someone pick, because the first mistake is invisible and the second is not.
    """
    by_alias: dict[str, str] = {}
    for field, spec in IMPORTABLE_FIELDS.items():
        by_alias[_normalise(spec["label"])] = field
        by_alias[_normalise(field)] = field
        for alias in spec.get("aliases", ()):
            by_alias.setdefault(_normalise(alias), field)

    mapping: dict[str, str] = {}
    taken: set[str] = set()
    for column in columns:
        matched = by_alias.get(_normalise(column))
        # One column per field: two columns both claiming "phone" would have the
        # second silently overwrite the first.
        if matched and matched not in taken:
            mapping[column] = matched
            taken.add(matched)
    return mapping


def parse_upload(file_obj) -> tuple[list[str], list[dict[str, str]]]:
    """Read a CSV/.xlsx upload into ``(columns, rows)``.

    Raises ``ImportError_`` for anything a person can fix (wrong file type, no
    header row, too many rows) so the console can say what to do about it.
    """
    suffix = Path(file_obj.name or "").suffix.lower()
    if suffix in CSV_EXTENSIONS:
        return _parse_csv(file_obj)
    if suffix in EXCEL_EXTENSIONS:
        return _parse_excel(file_obj)
    if suffix == ".xls":
        raise ImportError_(
            "LEGACY_EXCEL",
            "The old .xls format is not supported. Open it and save as .xlsx or CSV.",
        )
    raise ImportError_("UNSUPPORTED_FILE", "Upload a .csv or .xlsx file.")


def _decode(raw: bytes) -> str:
    """Text from a spreadsheet's bytes.

    utf-8-sig first because Excel writes a BOM and csv would otherwise read the
    first header as "﻿Business". cp1256 is the fallback rather than latin-1:
    these lists are Egyptian and carry Arabic business names, which cp1256
    decodes and latin-1 turns into mojibake. Errors are replaced, never raised —
    one bad byte must not cost the whole file.
    """
    for encoding in ("utf-8-sig", "cp1256"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _parse_csv(file_obj) -> tuple[list[str], list[dict[str, str]]]:
    text = _decode(file_obj.read())
    try:
        # Sniff the delimiter: exports from Excel in a European locale use ';'
        # and reading those with ',' yields one giant column and a useless
        # "no columns found" error.
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel  # a single-column file sniffs as nothing; ',' is fine

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    columns = [c.strip() for c in (reader.fieldnames or []) if c and c.strip()]
    if not columns:
        raise ImportError_("NO_COLUMNS", "This file has no header row.")

    rows: list[dict[str, str]] = []
    for row in reader:
        if len(rows) >= MAX_ROWS:
            raise ImportError_(
                "TOO_MANY_ROWS", f"This file has more than {MAX_ROWS:,} rows — split it up."
            )
        rows.append({c: _clean(row.get(c)) for c in columns})
    return columns, rows


def _parse_excel(file_obj) -> tuple[list[str], list[dict[str, str]]]:
    import openpyxl

    try:
        # read_only streams rather than building the whole sheet in memory;
        # data_only returns a formula's cached value instead of "=VLOOKUP(...)".
        book = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises a zoo of types for a bad file
        raise ImportError_("UNREADABLE_EXCEL", "This file could not be read as an .xlsx.") from exc

    try:
        sheet = book.worksheets[0]  # the first sheet; a picker is not worth it yet
        rows_iter = sheet.iter_rows(values_only=True)
        header = next(rows_iter, None)
        if not header:
            raise ImportError_("NO_COLUMNS", "This file has no header row.")

        columns = [str(c).strip() for c in header if c is not None and str(c).strip()]
        if not columns:
            raise ImportError_("NO_COLUMNS", "This file has no header row.")

        rows: list[dict[str, str]] = []
        for values in rows_iter:
            # openpyxl pads trailing empties with None; a wholly blank line is
            # the spreadsheet equivalent of whitespace, so skip rather than
            # count it as a failure in the summary.
            if values is None or all(v is None or str(v).strip() == "" for v in values):
                continue
            if len(rows) >= MAX_ROWS:
                raise ImportError_(
                    "TOO_MANY_ROWS", f"This file has more than {MAX_ROWS:,} rows — split it up."
                )
            # strict=False on purpose: a real sheet has rows with trailing
            # empties trimmed off and rows with a stray value past the last
            # header. Truncating to the shorter of the two keeps both importable
            # rather than raising and killing the file.
            rows.append({c: _clean(v) for c, v in zip(columns, values, strict=False)})
        return columns, rows
    finally:
        book.close()  # read_only workbooks hold the file handle open


def _clean(value: Any) -> str:
    """A cell as trimmed text. Numbers come back from Excel as floats, so a
    phone number in a numeric column arrives as 1000000000.0 — a lead nobody
    can call. Render whole floats without the tail."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def validate_mapping(mapping: dict[str, str]) -> None:
    """Refuse a mapping that cannot produce a usable lead."""
    fields = set(mapping.values())
    unknown = fields - set(IMPORTABLE_FIELDS)
    if unknown:
        raise ImportError_("UNKNOWN_FIELD", f"Cannot import into: {', '.join(sorted(unknown))}.")

    missing = [IMPORTABLE_FIELDS[f]["label"] for f in REQUIRED_FIELDS if f not in fields]
    if missing:
        raise ImportError_(
            "MISSING_REQUIRED",
            f"Map a column to {' and '.join(missing)} — a lead needs them.",
        )

    duplicated = [f for f in fields if list(mapping.values()).count(f) > 1]
    if duplicated:
        raise ImportError_(
            "DUPLICATE_FIELD",
            f"Two columns are mapped to {IMPORTABLE_FIELDS[duplicated[0]]['label']}.",
        )


def _category_slug(value: str) -> str:
    """Match a category cell to a configured category, by slug or by label.

    Unmatched categories are dropped rather than invented: creating CrmChoice
    rows from a spreadsheet would let one messy import fill everyone's dropdown
    with "cafe ", "Café " and "CAFE" forever.
    """
    if not value:
        return ""
    probe = _normalise(value)
    for choice in CrmChoice.objects.filter(kind=crm.CrmChoiceKind.CATEGORY, is_active=True):
        if _normalise(choice.slug) == probe or _normalise(choice.label) == probe:
            return choice.slug
    return ""


def import_rows(
    rows: list[dict[str, str]],
    mapping: dict[str, str],
    *,
    actor: AdminUser,
    source: str = crm.LeadSource.OTHER,
    assigned_sales: AdminUser | None = None,
    skip_duplicates: bool = True,
) -> dict:
    """Create a lead per row. Returns a summary; never raises for a bad row.

    Deliberately not atomic across rows. An import is a batch of independent
    facts, and rolling back three hundred good leads because row 301 has a
    malformed email would be obviously wrong. Each row is its own transaction.
    """
    validate_mapping(mapping)

    created = 0
    skipped: list[dict] = []
    failed: list[dict] = []

    for index, row in enumerate(rows, start=2):  # row 1 is the header, as a human counts
        fields = _row_to_fields(row, mapping)

        if not fields.get("business_name") or not fields.get("phone"):
            failed.append({"row": index, "reason": "Missing business name or phone."})
            continue

        if skip_duplicates:
            existing = crm_service.find_duplicates(
                phone=fields.get("phone", ""),
                email=fields.get("email", ""),
                business_name=fields.get("business_name", ""),
            ).first()
            if existing is not None:
                skipped.append(
                    {
                        "row": index,
                        "business_name": fields["business_name"],
                        "reason": "Already in the pipeline.",
                        "lead_id": str(existing.id),
                    }
                )
                continue

        try:
            with transaction.atomic():
                crm_service.create_manual_lead(
                    actor=actor,
                    source=source,
                    assigned_sales=assigned_sales,
                    **fields,
                )
            created += 1
        except Exception as exc:  # noqa: BLE001 — one row must not end the import
            failed.append({"row": index, "reason": _reason(exc)})

    return {
        "created": created,
        "skipped": len(skipped),
        "failed": len(failed),
        "total": len(rows),
        # Capped: a 5,000-row file of duplicates would otherwise return a 5,000
        # entry response nobody reads.
        "skipped_rows": skipped[:50],
        "failed_rows": failed[:50],
    }


def _row_to_fields(row: dict[str, str], mapping: dict[str, str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for column, field in mapping.items():
        value = (row.get(column) or "").strip()
        if not value:
            continue
        if field == "category":
            value = _category_slug(value)
            if not value:
                continue
        limit = _MAX_LEN.get(field)
        fields[field] = value[:limit] if limit else value

    # An email the model would reject costs the whole row otherwise. Dropping a
    # junk email keeps a lead that is still worth calling — the phone is what
    # Sales actually needs.
    email = fields.get("email", "")
    if email and "@" not in email:
        fields.pop("email")

    # Same for a URL column holding a bare domain or a hyphen.
    for field in ("website", "google_maps_url"):
        value = fields.get(field, "")
        if value and not value.lower().startswith(("http://", "https://")):
            if "." in value and " " not in value:
                fields[field] = f"https://{value}"
            else:
                fields.pop(field)

    return fields


def _reason(exc: Exception) -> str:
    """A row failure in words a salesperson can act on."""
    from django.core.exceptions import ValidationError

    if isinstance(exc, ValidationError):
        return "; ".join(exc.messages)
    text = str(exc)
    return text[:200] if text else exc.__class__.__name__


def preview(file_obj) -> dict:
    """What the console shows before anything is written."""
    if file_obj is None:
        raise UnprocessableEntity("No file provided.")

    columns, rows = parse_upload(file_obj)
    if not rows:
        raise ImportError_("NO_ROWS", "This file has a header but no rows.")

    mapping = suggest_mapping(columns)
    return {
        "columns": columns,
        "suggested_mapping": mapping,
        "total_rows": len(rows),
        "sample": rows[:PREVIEW_ROWS],
        "fields": [
            {"field": f, "label": spec["label"], "required": bool(spec.get("required"))}
            for f, spec in IMPORTABLE_FIELDS.items()
        ],
        # Named so the console can warn before the human maps anything.
        "unmapped_required": [
            IMPORTABLE_FIELDS[f]["label"] for f in REQUIRED_FIELDS if f not in mapping.values()
        ],
    }


def existing_phone_count(rows: list[dict[str, str]], mapping: dict[str, str]) -> int:
    """How many rows are already in the pipeline, by phone. Cheap enough to run
    at preview time so the console can say "40 of these 200 are duplicates"
    before anyone commits."""
    phone_column = next((c for c, f in mapping.items() if f == "phone"), None)
    if not phone_column:
        return 0
    phones = {(r.get(phone_column) or "").strip() for r in rows}
    phones.discard("")
    if not phones:
        return 0
    return Lead.objects.filter(phone__in=phones).count()
