"""CSV, Excel and JSON exports of generated leads.

Exports are flat and readable rather than a dump of the schema: the file lands
in a spreadsheet a salesperson opens, so columns are named the way a human would
say them and nested data is joined into one cell rather than serialised as JSON
a reader has to decode.

Streamed row by row. A 1,000-lead export built in memory is survivable, but the
same code is what a 10,000-lead export would use, and the difference between a
generator and a list here is the difference between a slow response and a dead
worker.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from django.http import HttpResponse, StreamingHttpResponse

COLUMNS: tuple[tuple[str, str], ...] = (
    ("business_name", "Business"),
    ("category", "Category"),
    ("address", "Address"),
    ("city", "City"),
    ("phone", "Phone"),
    ("phone_verified", "Phone verified"),
    ("email", "Email"),
    ("website", "Website"),
    ("instagram", "Instagram"),
    ("facebook", "Facebook"),
    ("rating", "Rating"),
    ("reviews_count", "Reviews"),
    ("branch_count", "Branches"),
    ("fit_score", "Fit score"),
    ("score_label", "Band"),
    ("owner_name", "Owner"),
    ("owner_name_source", "Owner source"),
    ("owner_name_confidence", "Owner confidence"),
    ("state", "State"),
    ("in_crm", "Already in CRM"),
    ("imported_at", "Imported at"),
    ("google_maps_url", "Google Maps"),
)


def export_queryset(queryset):
    """Attach everything the rows need, so exporting is not N+1 per lead."""
    return queryset.select_related("job", "website_profile").prefetch_related(
        "socials", "verifications"
    )


def row_for(lead) -> dict:
    """One lead, flattened. Absent values are empty strings, never "None".

    A spreadsheet full of the string "None" is the classic export tell; blank
    reads correctly to both a human and to Excel.
    """
    profile = getattr(lead, "website_profile", None)
    socials = {s.platform: s.url for s in lead.socials.all()}
    phone_check = next(
        (v for v in lead.verifications.all() if v.kind == "phone"), None
    )

    return {
        "business_name": lead.business_name,
        "category": lead.category_display,
        "address": lead.address,
        "city": lead.job.city if lead.job_id else "",
        "phone": lead.phone_e164 or lead.phone,
        # The distinction the whole verification design rests on: "possible"
        # means plausible, not confirmed, and an export must not blur it.
        "phone_verified": phone_check.result if phone_check else "",
        "email": (profile.emails[0] if profile and profile.emails else ""),
        "website": lead.website if lead.website_domain else "",
        "instagram": socials.get("instagram", ""),
        "facebook": socials.get("facebook", ""),
        "rating": lead.rating if lead.rating is not None else "",
        "reviews_count": lead.reviews_count,
        "branch_count": lead.branch_count,
        "fit_score": lead.fit_score,
        "score_label": lead.score_label,
        "owner_name": lead.owner_name,
        "owner_name_source": lead.owner_name_source,
        "owner_name_confidence": lead.owner_name_confidence,
        "state": lead.state,
        "in_crm": "yes" if lead.crm_match_id else "no",
        "imported_at": lead.imported_at.isoformat() if lead.imported_at else "",
        "google_maps_url": lead.google_maps_url,
    }


def _filename(extension: str) -> str:
    return f"stampn-leads-{datetime.now():%Y%m%d-%H%M}.{extension}"


class _Echo:
    """A write-only file-like object, so csv can stream into a generator."""

    def write(self, value):
        return value


def to_csv(queryset) -> StreamingHttpResponse:
    writer = csv.writer(_Echo())
    headers = [label for _, label in COLUMNS]
    keys = [key for key, _ in COLUMNS]

    def rows():
        yield writer.writerow(headers)
        for lead in export_queryset(queryset).iterator(chunk_size=200):
            data = row_for(lead)
            yield writer.writerow([data[key] for key in keys])

    response = StreamingHttpResponse(rows(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{_filename("csv")}"'
    return response


def to_json(queryset) -> StreamingHttpResponse:
    def chunks():
        yield "["
        first = True
        for lead in export_queryset(queryset).iterator(chunk_size=200):
            yield ("" if first else ",") + json.dumps(row_for(lead), default=str)
            first = False
        yield "]"

    response = StreamingHttpResponse(chunks(), content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="{_filename("json")}"'
    return response


def to_xlsx(queryset) -> HttpResponse:
    """Excel, via the openpyxl already used by the CRM's lead import.

    Written in write-only mode, which streams rows to the file rather than
    holding a full worksheet object graph in memory.
    """
    from openpyxl import Workbook

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Leads")
    sheet.append([label for _, label in COLUMNS])

    keys = [key for key, _ in COLUMNS]
    for lead in export_queryset(queryset).iterator(chunk_size=200):
        data = row_for(lead)
        sheet.append([data[key] for key in keys])

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{_filename("xlsx")}"'
    return response


FORMATS = {"csv": to_csv, "json": to_json, "xlsx": to_xlsx}
