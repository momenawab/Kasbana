"""Lead import tests.

The interesting cases here are all about files as they actually arrive: a BOM
from Excel, semicolons because the exporter was in a European locale, a phone
number stored as a number, a blank line at row 73, Arabic business names, and a
header nobody agreed on.
"""

from __future__ import annotations

import io

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from console import crm
from console.auth import issue_admin_tokens
from console.crm_import import suggest_mapping
from console.crm_seed import ensure_seeded
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser, Lead

pytestmark = pytest.mark.django_db

PREVIEW = "/api/admin/v1/leads/import/preview"
IMPORT = "/api/admin/v1/leads/import"


@pytest.fixture(autouse=True)
def seeded_choices():
    ensure_seeded()


@pytest.fixture
def sales():
    a = AdminUser(email="sales@stampn.net", name="Nour Sales", role=AdminRole.SALES)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def read_only():
    a = AdminUser(email="ro@stampn.net", role=AdminRole.READ_ONLY)
    a.set_password("supersecret1")
    a.save()
    return a


def _admin(admin):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return c


def _csv(text: str, name: str = "leads.csv") -> SimpleUploadedFile:
    body = text if isinstance(text, bytes) else text.encode("utf-8")
    return SimpleUploadedFile(name, body, content_type="text/csv")


def _xlsx(rows: list[list], name: str = "leads.xlsx") -> SimpleUploadedFile:
    book = openpyxl.Workbook()
    for row in rows:
        book.active.append(row)
    buf = io.BytesIO()
    book.save(buf)
    return SimpleUploadedFile(
        name,
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


SIMPLE = "Business Name,Owner,Phone,Area\nBloom Café,Ali,01000000000,Zamalek\n"


def _mapping(**overrides) -> str:
    import json

    base = {"Business Name": "business_name", "Owner": "name", "Phone": "phone", "Area": "area"}
    base.update(overrides)
    return json.dumps(base)


# ── Column mapping ──────────────────────────────────────────────────────────
def test_mapping_is_suggested_from_however_the_column_was_named():
    assert suggest_mapping(["Business Name"]) == {"Business Name": "business_name"}
    assert suggest_mapping(["business_name"]) == {"business_name": "business_name"}
    assert suggest_mapping(["BUSINESS  NAME"]) == {"BUSINESS  NAME": "business_name"}
    assert suggest_mapping(["Company"]) == {"Company": "business_name"}
    assert suggest_mapping(["Mobile"]) == {"Mobile": "phone"}


def test_an_unrecognised_column_is_left_unmapped_rather_than_guessed():
    """A near-match that quietly loads phone numbers into the address field is
    worse than making someone pick — the first mistake is invisible."""
    assert suggest_mapping(["Revenue 2025", "Notes on file"]) == {}


def test_two_columns_cannot_claim_the_same_field():
    """The second would silently overwrite the first."""
    mapping = suggest_mapping(["Phone", "Mobile"])
    assert list(mapping.values()) == ["phone"]


def test_preview_reports_columns_sample_and_mapping(sales):
    res = _admin(sales).post(PREVIEW, {"file": _csv(SIMPLE)}, format="multipart")
    assert res.status_code == 200
    assert res.data["columns"] == ["Business Name", "Owner", "Phone", "Area"]
    assert res.data["total_rows"] == 1
    assert res.data["suggested_mapping"]["Phone"] == "phone"
    assert res.data["sample"][0]["Business Name"] == "Bloom Café"
    assert res.data["unmapped_required"] == []


def test_preview_names_the_required_fields_it_could_not_map(sales):
    res = _admin(sales).post(
        PREVIEW, {"file": _csv("Owner,Area\nAli,Zamalek\n")}, format="multipart"
    )
    assert res.status_code == 200
    assert set(res.data["unmapped_required"]) == {"Business", "Phone"}


def test_preview_writes_nothing(sales):
    _admin(sales).post(PREVIEW, {"file": _csv(SIMPLE)}, format="multipart")
    assert Lead.objects.count() == 0


def test_preview_counts_how_many_are_already_in_the_pipeline(sales):
    Lead.objects.create(business_name="Other", name="X", phone="01000000000")
    res = _admin(sales).post(PREVIEW, {"file": _csv(SIMPLE)}, format="multipart")
    assert res.data["existing_matches"] == 1


# ── Files as they actually arrive ───────────────────────────────────────────
def test_excel_bom_does_not_corrupt_the_first_header(sales):
    """Excel writes a UTF-8 BOM; read naively the first column becomes
    "﻿Business Name" and maps to nothing."""
    res = _admin(sales).post(
        PREVIEW, {"file": _csv(SIMPLE.encode("utf-8-sig"))}, format="multipart"
    )
    assert res.data["columns"][0] == "Business Name"
    assert res.data["suggested_mapping"]["Business Name"] == "business_name"


def test_semicolon_delimited_export_is_read(sales):
    """Excel in a European locale exports with ';'. Read with ',' the whole row
    is one column and the error is a baffling "no columns found"."""
    res = _admin(sales).post(
        PREVIEW,
        {"file": _csv("Business Name;Phone\nBloom Café;01000000000\n")},
        format="multipart",
    )
    assert res.data["columns"] == ["Business Name", "Phone"]


def test_arabic_business_names_survive(sales):
    res = _admin(sales).post(
        PREVIEW, {"file": _csv("Business Name,Phone\nمقهى بلوم,01000000000\n")}, format="multipart"
    )
    assert res.data["sample"][0]["Business Name"] == "مقهى بلوم"


def test_a_phone_stored_as_a_number_is_not_imported_as_a_float(sales):
    """Excel hands back 1000000000.0 for a numeric cell — a lead nobody can call."""
    file = _xlsx([["Business Name", "Phone"], ["Bloom Café", 1000000000]])
    res = _admin(sales).post(PREVIEW, {"file": file}, format="multipart")
    assert res.data["sample"][0]["Phone"] == "1000000000"


def test_xlsx_import_end_to_end(sales):
    import json

    file = _xlsx([["Business Name", "Phone", "Owner"], ["Bloom Café", "01000000000", "Ali"]])
    res = _admin(sales).post(
        IMPORT,
        {
            "file": file,
            "mapping": json.dumps(
                {"Business Name": "business_name", "Phone": "phone", "Owner": "name"}
            ),
        },
        format="multipart",
    )
    assert res.status_code == 201
    assert res.data["created"] == 1
    assert Lead.objects.get().business_name == "Bloom Café"


def test_blank_rows_are_skipped_not_counted_as_failures(sales):
    import json

    file = _xlsx(
        [
            ["Business Name", "Phone"],
            ["Bloom Café", "01000000000"],
            [None, None],
            ["", ""],
            ["Cairo Juice", "01000000001"],
        ]
    )
    res = _admin(sales).post(
        IMPORT,
        {"file": file, "mapping": json.dumps({"Business Name": "business_name", "Phone": "phone"})},
        format="multipart",
    )
    assert res.data == {**res.data, "created": 2, "failed": 0, "total": 2}


def test_a_legacy_xls_is_refused_with_advice(sales):
    file = SimpleUploadedFile(
        "leads.xls", b"\xd0\xcf\x11\xe0", content_type="application/vnd.ms-excel"
    )
    res = _admin(sales).post(PREVIEW, {"file": file}, format="multipart")
    assert res.status_code == 400
    assert res.data["error"]["code"] == "LEGACY_EXCEL"


def test_a_pdf_is_refused(sales):
    file = SimpleUploadedFile("leads.pdf", b"%PDF-1.4", content_type="application/pdf")
    res = _admin(sales).post(PREVIEW, {"file": file}, format="multipart")
    assert res.status_code == 400
    assert res.data["error"]["code"] == "UNSUPPORTED_FILE"


def test_a_file_with_only_a_header_is_refused(sales):
    res = _admin(sales).post(PREVIEW, {"file": _csv("Business Name,Phone\n")}, format="multipart")
    assert res.status_code == 400
    assert res.data["error"]["code"] == "NO_ROWS"


def test_no_file_is_a_clean_error(sales):
    res = _admin(sales).post(PREVIEW, {}, format="multipart")
    assert res.status_code in (400, 422)


# ── Importing ───────────────────────────────────────────────────────────────
def test_import_creates_leads_through_the_normal_manual_path(sales):
    """Imported leads must not be subtly different from typed ones: same
    provenance, same timeline entry, same score."""
    res = _admin(sales).post(
        IMPORT, {"file": _csv(SIMPLE), "mapping": _mapping()}, format="multipart"
    )
    assert res.status_code == 201

    lead = Lead.objects.get()
    assert lead.lead_type == crm.LeadType.MANUAL
    assert lead.created_by == sales
    assert lead.created_by_type == crm.LeadCreatedBy.SALES_USER
    assert lead.activities.get().kind == crm.ActivityKind.MANUAL_LEAD_CREATED
    assert lead.lead_score > 0
    assert AdminAuditLog.objects.filter(action="lead.import").exists()


def test_import_reports_a_summary(sales):
    csv_text = (
        "Business Name,Owner,Phone,Area\n"
        "Bloom Café,Ali,01000000000,Zamalek\n"
        "Cairo Juice,Sara,01000000001,Maadi\n"
    )
    res = _admin(sales).post(
        IMPORT, {"file": _csv(csv_text), "mapping": _mapping()}, format="multipart"
    )
    assert res.data["created"] == 2
    assert res.data["skipped"] == 0
    assert res.data["failed"] == 0
    assert res.data["total"] == 2


def test_duplicates_are_skipped_and_named(sales):
    Lead.objects.create(business_name="Other", name="X", phone="01000000000")
    res = _admin(sales).post(
        IMPORT, {"file": _csv(SIMPLE), "mapping": _mapping()}, format="multipart"
    )

    assert res.data["created"] == 0
    assert res.data["skipped"] == 1
    assert res.data["skipped_rows"][0]["business_name"] == "Bloom Café"
    assert res.data["skipped_rows"][0]["lead_id"]  # so the console can link to it
    assert Lead.objects.count() == 1


def test_duplicate_skipping_can_be_turned_off(sales):
    Lead.objects.create(business_name="Other", name="X", phone="01000000000")
    res = _admin(sales).post(
        IMPORT,
        {"file": _csv(SIMPLE), "mapping": _mapping(), "skip_duplicates": "false"},
        format="multipart",
    )
    assert res.data["created"] == 1
    assert Lead.objects.count() == 2


def test_a_row_missing_a_required_value_fails_alone(sales):
    """Row 3 is bad; rows 2 and 4 must still import."""
    csv_text = (
        "Business Name,Owner,Phone,Area\n"
        "Bloom Café,Ali,01000000000,Zamalek\n"
        ",Nobody,,Nowhere\n"
        "Cairo Juice,Sara,01000000001,Maadi\n"
    )
    res = _admin(sales).post(
        IMPORT, {"file": _csv(csv_text), "mapping": _mapping()}, format="multipart"
    )

    assert res.data["created"] == 2
    assert res.data["failed"] == 1
    assert res.data["failed_rows"][0]["row"] == 3  # as a human counts, header included
    assert Lead.objects.count() == 2


def test_a_junk_email_costs_the_email_not_the_lead(sales):
    """The phone is what Sales needs; losing the row over a malformed email
    would throw away a callable lead."""
    csv_text = "Business Name,Phone,Email\nBloom Café,01000000000,not-an-email\n"
    res = _admin(sales).post(
        IMPORT,
        {
            "file": _csv(csv_text),
            "mapping": '{"Business Name": "business_name", "Phone": "phone", "Email": "email"}',
        },
        format="multipart",
    )
    assert res.data["created"] == 1
    assert Lead.objects.get().email == ""


def test_a_bare_domain_is_made_into_a_url(sales):
    csv_text = "Business Name,Phone,Website\nBloom Café,01000000000,bloomcafe.com\n"
    res = _admin(sales).post(
        IMPORT,
        {
            "file": _csv(csv_text),
            "mapping": '{"Business Name": "business_name", "Phone": "phone", "Website": "website"}',
        },
        format="multipart",
    )
    assert res.data["created"] == 1
    assert Lead.objects.get().website == "https://bloomcafe.com"


def test_an_overlong_cell_is_truncated_rather_than_failing_the_row(sales):
    csv_text = f"Business Name,Phone\n{'x' * 400},01000000000\n"
    res = _admin(sales).post(
        IMPORT,
        {"file": _csv(csv_text), "mapping": '{"Business Name": "business_name", "Phone": "phone"}'},
        format="multipart",
    )
    assert res.data["created"] == 1
    assert len(Lead.objects.get().business_name) == 160


def test_a_category_that_matches_a_configured_one_is_linked(sales):
    csv_text = "Business Name,Phone,Type\nBloom Café,01000000000,Café\n"
    res = _admin(sales).post(
        IMPORT,
        {
            "file": _csv(csv_text),
            "mapping": '{"Business Name": "business_name", "Phone": "phone", "Type": "category"}',
        },
        format="multipart",
    )
    assert res.data["created"] == 1
    assert Lead.objects.get().category == "cafe"  # matched the seeded row by label


def test_an_unknown_category_is_dropped_not_invented(sales):
    """Creating CrmChoice rows from a spreadsheet would fill everyone's dropdown
    with "cafe ", "Café " and "CAFE" forever."""
    csv_text = "Business Name,Phone,Type\nBloom Café,01000000000,Underwater Basket Weaving\n"
    res = _admin(sales).post(
        IMPORT,
        {
            "file": _csv(csv_text),
            "mapping": '{"Business Name": "business_name", "Phone": "phone", "Type": "category"}',
        },
        format="multipart",
    )
    assert res.data["created"] == 1
    assert Lead.objects.get().category == ""


def test_the_importer_chooses_the_source_and_owner(sales):
    res = _admin(sales).post(
        IMPORT,
        {
            "file": _csv(SIMPLE),
            "mapping": _mapping(),
            "source": "google_maps",
            "assigned_sales": str(sales.id),
        },
        format="multipart",
    )
    assert res.status_code == 201
    lead = Lead.objects.get()
    assert lead.source == "google_maps"
    assert lead.assigned_sales == sales


# ── Mapping validation ──────────────────────────────────────────────────────
def test_a_mapping_without_the_required_fields_is_refused(sales):
    res = _admin(sales).post(
        IMPORT, {"file": _csv(SIMPLE), "mapping": '{"Area": "area"}'}, format="multipart"
    )
    assert res.status_code == 400
    assert res.data["error"]["code"] == "MISSING_REQUIRED"
    assert Lead.objects.count() == 0


def test_a_mapping_into_a_field_that_is_not_importable_is_refused(sales):
    """lead_score, status and the rest are the pipeline's, not a spreadsheet's."""
    res = _admin(sales).post(
        IMPORT,
        {
            "file": _csv(SIMPLE),
            "mapping": '{"Business Name": "business_name", "Phone": "phone", "Area": "lead_score"}',
        },
        format="multipart",
    )
    assert res.status_code == 400
    assert res.data["error"]["code"] == "UNKNOWN_FIELD"


def test_malformed_mapping_json_is_a_clean_error(sales):
    res = _admin(sales).post(IMPORT, {"file": _csv(SIMPLE), "mapping": "{oops"}, format="multipart")
    assert res.status_code == 400
    assert res.data["error"]["code"] == "BAD_MAPPING"


# ── Permissions ─────────────────────────────────────────────────────────────
def test_a_read_only_admin_cannot_import(read_only):
    assert (
        _admin(read_only)
        .post(IMPORT, {"file": _csv(SIMPLE), "mapping": _mapping()}, format="multipart")
        .status_code
        == 403
    )
    assert Lead.objects.count() == 0


def test_a_read_only_admin_cannot_even_preview(read_only):
    assert (
        _admin(read_only).post(PREVIEW, {"file": _csv(SIMPLE)}, format="multipart").status_code
        == 403
    )


def test_import_requires_auth():
    assert APIClient().post(IMPORT, {"file": _csv(SIMPLE)}, format="multipart").status_code in (
        401,
        403,
    )
