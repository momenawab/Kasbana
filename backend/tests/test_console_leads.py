"""Lead CRM tests.

Covers the public (unauthenticated) intake from the marketing site — including
validation and the bot honeypot — plus the console pipeline: manual creation,
duplicate detection, the activity timeline, call logging, scoring, the KPI
cards, and the guards on the configurable dropdowns.

The intake tests double as the regression suite for the pre-CRM behaviour: the
marketing form's contract must not shift underneath it just because the lead it
creates grew forty fields.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from console import crm
from console.auth import issue_admin_tokens
from console.crm_seed import ensure_seeded
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser, CrmChoice, Lead, LeadActivity, LeadCall

pytestmark = pytest.mark.django_db

PUBLIC = "/api/v1/leads"
ADMIN = "/api/admin/v1/leads"
CHOICES = "/api/admin/v1/crm/choices"

VALID = {
    "name": "Ali Hassan",
    "email": "ali@bloomcafe.com",
    "phone": "01000000000",
    "business_name": "Bloom Café",
}


@pytest.fixture(autouse=True)
def seeded_choices():
    """Every CRM write validates against the dropdown rows that the 0014
    migration seeds. Seed explicitly rather than lean on migrations having run
    against the test database."""
    ensure_seeded()


@pytest.fixture
def super_admin():
    a = AdminUser(email="super@stampn.net", role=AdminRole.SUPER_ADMIN)
    a.set_password("supersecret1")
    a.save()
    return a


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


def _manual(**overrides) -> dict:
    return {"business_name": "Cairo Juice", "name": "Sara", "phone": "01111111111", **overrides}


# ── Public intake — the pre-CRM contract, unchanged ─────────────────────────
def test_public_can_create_lead_without_auth():
    res = APIClient().post(PUBLIC, VALID, format="json")
    assert res.status_code == 201
    lead = Lead.objects.get()
    assert lead.business_name == "Bloom Café"
    assert lead.status == crm.LeadStatus.NEW_LEAD


def test_missing_fields_rejected():
    res = APIClient().post(PUBLIC, {"name": "Ali"}, format="json")
    assert res.status_code == 400
    assert Lead.objects.count() == 0


def test_public_intake_still_requires_email_though_the_model_allows_blank():
    """The model relaxed email for walk-in manual leads; the marketing form did
    not — a website lead with no reply address is a dead one."""
    res = APIClient().post(PUBLIC, {**VALID, "email": ""}, format="json")
    assert res.status_code == 400
    assert Lead.objects.count() == 0


def test_honeypot_is_accepted_but_saves_nothing():
    res = APIClient().post(PUBLIC, {**VALID, "botcheck": "spam"}, format="json")
    assert res.status_code == 201
    assert Lead.objects.count() == 0


# ── Website leads are born fully formed ─────────────────────────────────────
def test_website_lead_is_stamped_with_its_provenance_automatically():
    APIClient().post(PUBLIC, VALID, format="json")
    lead = Lead.objects.get()

    assert lead.lead_type == crm.LeadType.WEBSITE
    assert lead.source == crm.LeadSource.WEBSITE
    assert lead.created_by_type == crm.LeadCreatedBy.SYSTEM
    assert lead.created_by is None
    assert lead.assigned_sales is None
    assert lead.status == crm.LeadStatus.NEW_LEAD
    assert lead.priority == crm.LeadPriority.MEDIUM
    assert lead.temperature == crm.LeadTemperature.WARM
    assert lead.last_activity == "Website Form Submitted"


def test_website_lead_starts_at_score_25():
    """25 is not stamped — it is what medium + warm + a website submission
    computes to. Re-scoring a fresh website lead must therefore not move it."""
    APIClient().post(PUBLIC, VALID, format="json")
    lead = Lead.objects.get()
    assert lead.lead_score == 25
    assert lead.recalculate_score() == 25


def test_website_lead_gets_a_timeline_entry_with_no_admin_behind_it():
    APIClient().post(PUBLIC, VALID, format="json")
    activity = LeadActivity.objects.get()
    assert activity.kind == crm.ActivityKind.WEBSITE_FORM_SUBMITTED
    assert activity.actor is None
    assert activity.actor_label == "System"


# ── Manual leads ────────────────────────────────────────────────────────────
def test_sales_can_add_a_lead_by_hand(sales):
    res = _admin(sales).post(ADMIN, _manual(), format="json")
    assert res.status_code == 201

    lead = Lead.objects.get()
    assert lead.lead_type == crm.LeadType.MANUAL
    assert lead.source == crm.LeadSource.MANUAL
    assert lead.created_by_type == crm.LeadCreatedBy.SALES_USER
    assert lead.created_by == sales
    assert lead.activities.get().kind == crm.ActivityKind.MANUAL_LEAD_CREATED
    assert AdminAuditLog.objects.filter(action="lead.create").exists()


def test_manual_lead_keeps_the_source_sales_chose(sales):
    _admin(sales).post(ADMIN, _manual(source="walk_in"), format="json")
    lead = Lead.objects.get()
    assert lead.source == "walk_in"
    assert lead.lead_type == crm.LeadType.MANUAL  # type is still not the caller's to pick


def test_manual_lead_needs_no_email(sales):
    res = _admin(sales).post(ADMIN, _manual(), format="json")
    assert res.status_code == 201
    assert Lead.objects.get().email == ""


def test_manual_lead_needs_no_owner_name(sales):
    """A walk-in is often a shop name and a phone number; the owner's name comes
    later. The Add Lead form marks it optional, so the write shape must agree."""
    payload = _manual()
    del payload["name"]
    res = _admin(sales).post(ADMIN, payload, format="json")
    assert res.status_code == 201
    assert Lead.objects.get().name == ""


def test_client_cannot_forge_provenance_or_score(sales):
    """lead_type / created_by / lead_score are the system's to decide. A client
    that claims them must be ignored, not obeyed."""
    _admin(sales).post(
        ADMIN,
        _manual(lead_type="website", created_by_type="system", lead_score=99),
        format="json",
    )
    lead = Lead.objects.get()
    assert lead.lead_type == crm.LeadType.MANUAL
    assert lead.created_by_type == crm.LeadCreatedBy.SALES_USER
    assert lead.lead_score == 20  # medium + warm, no website bonus


def test_read_only_admin_cannot_add_a_lead(read_only):
    assert _admin(read_only).post(ADMIN, _manual(), format="json").status_code == 403


def test_read_only_admin_can_still_see_the_pipeline(read_only):
    Lead.objects.create(**VALID)
    assert _admin(read_only).get(ADMIN).status_code == 200


# ── Duplicate detection ─────────────────────────────────────────────────────
def test_duplicate_phone_warns_instead_of_creating(sales):
    Lead.objects.create(business_name="Other", name="X", phone="01111111111")
    res = _admin(sales).post(ADMIN, _manual(), format="json")

    assert res.status_code == 409
    assert res.data["error"]["code"] == "POSSIBLE_DUPLICATE"
    assert len(res.data["error"]["duplicates"]) == 1
    assert Lead.objects.count() == 1  # nothing created


def test_duplicate_business_name_matches_whole_and_case_insensitively(sales):
    Lead.objects.create(business_name="cairo juice", name="X", phone="09999999999")
    assert _admin(sales).post(ADMIN, _manual(), format="json").status_code == 409


def test_a_name_that_merely_contains_an_existing_one_is_not_a_duplicate(sales):
    """ "Bloom" must not collide with every café in Cairo whose name contains it."""
    Lead.objects.create(business_name="Bloom", name="X", phone="09999999999")
    res = _admin(sales).post(
        ADMIN, _manual(business_name="Bloom Café Downtown", phone="08888888888"), format="json"
    )
    assert res.status_code == 201


def test_create_anyway_overrides_the_duplicate_warning(sales):
    Lead.objects.create(business_name="Other", name="X", phone="01111111111")
    res = _admin(sales).post(ADMIN, _manual(force=True), format="json")
    assert res.status_code == 201
    assert Lead.objects.count() == 2


def test_duplicate_probe_endpoint_finds_matches(sales):
    Lead.objects.create(business_name="Other", name="X", phone="01111111111")
    res = _admin(sales).get(f"{ADMIN}/duplicates?phone=01111111111")
    assert res.status_code == 200
    assert len(res.data) == 1


# ── The timeline ────────────────────────────────────────────────────────────
def test_status_change_lands_on_the_timeline_with_both_ends_of_the_move(sales):
    lead = Lead.objects.create(**_manual())
    res = _admin(sales).patch(f"{ADMIN}/{lead.id}", {"status": "interested"}, format="json")
    assert res.status_code == 200

    activity = lead.activities.get(kind=crm.ActivityKind.STATUS_CHANGED)
    assert activity.description == "New Lead → Interested"
    assert activity.actor == sales
    assert activity.actor_label == "Nour Sales"


def test_contacting_a_lead_stamps_contacted_at(sales):
    """The old model's one signal. It still has to mean what it always meant."""
    lead = Lead.objects.create(**_manual())
    _admin(sales).patch(f"{ADMIN}/{lead.id}", {"status": "owner_answered"}, format="json")

    lead.refresh_from_db()
    assert lead.contacted_at is not None


def test_assignment_change_is_logged_by_name(sales, super_admin):
    lead = Lead.objects.create(**_manual())
    _admin(super_admin).patch(
        f"{ADMIN}/{lead.id}", {"assigned_sales": str(sales.id)}, format="json"
    )

    activity = lead.activities.get(kind=crm.ActivityKind.ASSIGNED_SALES_CHANGED)
    assert activity.description == "— → Nour Sales"


def test_an_untracked_field_change_does_not_clutter_the_timeline(sales):
    lead = Lead.objects.create(**_manual())
    _admin(sales).patch(f"{ADMIN}/{lead.id}", {"address": "12 Nile St"}, format="json")
    assert lead.activities.count() == 0


def test_timeline_is_newest_first(sales):
    lead = Lead.objects.create(**_manual())
    _admin(sales).patch(f"{ADMIN}/{lead.id}", {"status": "interested"}, format="json")
    _admin(sales).patch(f"{ADMIN}/{lead.id}", {"priority": "high"}, format="json")

    res = _admin(sales).get(f"{ADMIN}/{lead.id}")
    kinds = [a["kind"] for a in res.data["activities"]]
    assert kinds[0] == crm.ActivityKind.PRIORITY_CHANGED


def test_detail_response_includes_the_activity_just_written(sales):
    """A PATCH must return the timeline including its own entry — the naive
    implementation serialises a prefetch taken before the write and omits it."""
    lead = Lead.objects.create(**_manual())
    res = _admin(sales).patch(f"{ADMIN}/{lead.id}", {"status": "interested"}, format="json")
    assert any(a["kind"] == crm.ActivityKind.STATUS_CHANGED for a in res.data["activities"])


# ── Calls ───────────────────────────────────────────────────────────────────
def test_logging_a_call_records_it_and_moves_the_lead(sales):
    lead = Lead.objects.create(**_manual())
    called_at = timezone.now()
    follow_up = called_at + timedelta(days=2)

    res = _admin(sales).post(
        f"{ADMIN}/{lead.id}/calls",
        {
            "called_at": called_at.isoformat(),
            "duration_seconds": 180,
            "result": "owner_answered",
            "contact_method": "phone",
            "next_follow_up_at": follow_up.isoformat(),
            "notes": "Wants a demo Sunday.",
        },
        format="json",
    )
    assert res.status_code == 201

    lead.refresh_from_db()
    assert LeadCall.objects.count() == 1
    assert lead.last_contact_at == called_at
    assert lead.next_follow_up_at == follow_up
    assert lead.contacted_at is not None


def test_a_logged_call_appears_on_the_timeline(sales):
    lead = Lead.objects.create(**_manual())
    _admin(sales).post(
        f"{ADMIN}/{lead.id}/calls",
        {"called_at": timezone.now().isoformat(), "duration_seconds": 180, "result": "busy"},
        format="json",
    )
    activity = lead.activities.get(kind=crm.ActivityKind.PHONE_CALL_LOGGED)
    assert "Busy" in activity.description
    assert "3 min" in activity.description


def test_calls_raise_the_score(sales):
    lead = Lead.objects.create(**_manual())
    before = lead.recalculate_score()
    _admin(sales).post(
        f"{ADMIN}/{lead.id}/calls",
        {"called_at": timezone.now().isoformat(), "result": "no_answer"},
        format="json",
    )
    lead.refresh_from_db()
    assert lead.lead_score > before


def test_invalid_call_result_rejected(sales):
    lead = Lead.objects.create(**_manual())
    res = _admin(sales).post(
        f"{ADMIN}/{lead.id}/calls",
        {"called_at": timezone.now().isoformat(), "result": "went_great"},
        format="json",
    )
    assert res.status_code == 400


# ── Scoring ─────────────────────────────────────────────────────────────────
def test_score_stays_within_bounds_when_every_signal_fires():
    """Every weight firing at once lands on exactly 100 — the scale is designed
    to reach its own top, so a full bar means something."""
    lead = Lead.objects.create(**_manual(), lead_type="website", priority="high", temperature="hot")
    for kind in (crm.ActivityKind.DEMO_SCHEDULED, crm.ActivityKind.PROPOSAL_SENT):
        LeadActivity.objects.create(lead=lead, kind=kind, title=kind, actor_label="System")
    for _ in range(8):  # more calls than the cap scores
        LeadCall.objects.create(lead=lead, called_at=timezone.now(), result="answered")

    assert lead.recalculate_score() == 100


def test_creating_a_lead_is_not_engagement_and_earns_no_recency_points():
    """Every lead is born with a creation entry dated now. If that counted as
    recent activity, every lead would get the bonus at birth and the signal
    would mean "was created recently" rather than "is being worked"."""
    APIClient().post(PUBLIC, VALID, format="json")
    website = Lead.objects.get()
    assert website.lead_score == 25  # not 35

    website.activities.create(
        kind=crm.ActivityKind.EMAIL_SENT, title="Email Sent", actor_label="System"
    )
    assert website.recalculate_score() == 35  # a real touch does earn them


def test_milestone_points_survive_the_status_moving_on(sales):
    """A lead that reached Proposal Sent and progressed to Negotiation keeps the
    credit — the milestone happened, and scoring reads the timeline, not the
    current status."""
    lead = Lead.objects.create(**_manual())
    _admin(sales).patch(f"{ADMIN}/{lead.id}", {"status": "proposal_sent"}, format="json")
    lead.refresh_from_db()
    with_proposal = lead.lead_score

    _admin(sales).patch(f"{ADMIN}/{lead.id}", {"status": "negotiation"}, format="json")
    lead.refresh_from_db()
    assert lead.lead_score == with_proposal


def test_scoring_an_unsaved_lead_does_not_explode():
    """``score_lead`` runs on a Lead with no pk during creation, when the related
    managers it reads would raise."""
    assert crm.score_lead(Lead(priority="high", temperature="hot")) == 45


# ── Filters, search, sort ───────────────────────────────────────────────────
def test_filter_by_lead_type(sales):
    APIClient().post(PUBLIC, VALID, format="json")
    Lead.objects.create(**_manual(), lead_type="manual")

    res = _admin(sales).get(f"{ADMIN}?lead_type=website")
    assert len(res.data["results"]) == 1
    assert res.data["results"][0]["lead_type"] == "website"


def test_filter_accepts_several_values_for_one_field(sales):
    Lead.objects.create(**_manual(phone="1"), status="interested")
    Lead.objects.create(**_manual(phone="2"), status="hot_lead")
    Lead.objects.create(**_manual(phone="3"), status="closed")

    res = _admin(sales).get(f"{ADMIN}?status=interested&status=hot_lead")
    assert len(res.data["results"]) == 2


def test_cleared_filter_means_everything_not_nothing(sales):
    """The console sends ?status= when a user clears a chip."""
    Lead.objects.create(**_manual())
    res = _admin(sales).get(f"{ADMIN}?status=")
    assert len(res.data["results"]) == 1


def test_unassigned_filter(sales):
    Lead.objects.create(**_manual(phone="1"))
    Lead.objects.create(**_manual(phone="2"), assigned_sales=sales)

    res = _admin(sales).get(f"{ADMIN}?unassigned=1")
    assert len(res.data["results"]) == 1


def test_global_search_spans_business_owner_and_phone(sales):
    Lead.objects.create(**_manual(business_name="Bloom Café", phone="0100"))
    Lead.objects.create(**_manual(business_name="Other", name="Zed", phone="0200"))

    assert len(_admin(sales).get(f"{ADMIN}?q=bloom").data["results"]) == 1
    assert len(_admin(sales).get(f"{ADMIN}?q=Zed").data["results"]) == 1
    assert len(_admin(sales).get(f"{ADMIN}?q=0200").data["results"]) == 1


def test_sort_by_score_descending(sales):
    Lead.objects.create(**_manual(phone="1"), lead_score=10)
    Lead.objects.create(**_manual(phone="2"), lead_score=90)

    res = _admin(sales).get(f"{ADMIN}?sort=-lead_score")
    assert [r["lead_score"] for r in res.data["results"]] == [90, 10]


def test_unknown_sort_column_falls_back_rather_than_500ing(sales):
    Lead.objects.create(**_manual())
    assert _admin(sales).get(f"{ADMIN}?sort=password").status_code == 200


def test_malformed_date_filter_is_ignored_not_fatal(sales):
    Lead.objects.create(**_manual())
    res = _admin(sales).get(f"{ADMIN}?created_from=not-a-date")
    assert res.status_code == 200
    assert len(res.data["results"]) == 1


def test_created_to_includes_the_whole_day_picked(sales):
    lead = Lead.objects.create(**_manual())
    today = timezone.localtime(lead.created_at).date().isoformat()
    res = _admin(sales).get(f"{ADMIN}?created_to={today}")
    assert len(res.data["results"]) == 1


# ── KPI cards ───────────────────────────────────────────────────────────────
def test_kpis_count_the_pipeline(sales):
    APIClient().post(PUBLIC, VALID, format="json")
    Lead.objects.create(**_manual(phone="1"), lead_type="manual", status="interested")
    Lead.objects.create(**_manual(phone="2"), lead_type="manual", status="demo_scheduled")

    data = _admin(sales).get(f"{ADMIN}/kpis").data
    assert data["total"] == 3
    assert data["website"] == 1
    assert data["manual"] == 2
    assert data["interested"] == 1
    assert data["demo_scheduled"] == 1


def test_overdue_follow_ups_skip_leads_that_are_already_done(sales):
    """Chasing a lead that said "do not call again" is not a task."""
    past = timezone.now() - timedelta(days=3)
    Lead.objects.create(**_manual(phone="1"), next_follow_up_at=past, status="interested")
    Lead.objects.create(**_manual(phone="2"), next_follow_up_at=past, status="do_not_call_again")

    assert _admin(sales).get(f"{ADMIN}/kpis").data["overdue_follow_ups"] == 1


def test_the_overdue_card_and_its_drill_down_agree(sales):
    """Clicking a card reading 3 must not list 5 rows. The count and the filter
    share one predicate precisely so this cannot drift."""
    past = timezone.now() - timedelta(days=3)
    Lead.objects.create(**_manual(phone="1"), next_follow_up_at=past, status="interested")
    Lead.objects.create(**_manual(phone="2"), next_follow_up_at=past, status="hot_lead")
    Lead.objects.create(**_manual(phone="3"), next_follow_up_at=past, status="do_not_call_again")
    Lead.objects.create(**_manual(phone="4"))  # no follow-up at all

    card = _admin(sales).get(f"{ADMIN}/kpis").data["overdue_follow_ups"]
    rows = _admin(sales).get(f"{ADMIN}?overdue=1").data["results"]
    assert card == 2
    assert len(rows) == card


def test_the_todays_follow_ups_card_and_its_drill_down_agree(sales):
    now = timezone.now()
    Lead.objects.create(**_manual(phone="1"), next_follow_up_at=now)
    Lead.objects.create(**_manual(phone="2"), next_follow_up_at=now + timedelta(days=4))

    card = _admin(sales).get(f"{ADMIN}/kpis").data["follow_ups_today"]
    rows = _admin(sales).get(f"{ADMIN}?follow_up=today").data["results"]
    assert card == 1
    assert len(rows) == card


def test_conversion_rate_is_zero_not_a_crash_on_an_empty_pipeline(sales):
    assert _admin(sales).get(f"{ADMIN}/kpis").data["conversion_rate"] == 0.0


def test_kpis_describe_the_filtered_slice(sales):
    APIClient().post(PUBLIC, VALID, format="json")
    Lead.objects.create(**_manual(), lead_type="manual")

    data = _admin(sales).get(f"{ADMIN}/kpis?lead_type=manual").data
    assert data["total"] == 1


# ── Configurable dropdowns ──────────────────────────────────────────────────
def test_system_choices_are_seeded_for_every_enum():
    assert CrmChoice.objects.filter(kind="status", is_system=True).count() == len(
        crm.LeadStatus.values
    )
    assert CrmChoice.objects.filter(kind="category", is_system=False).exists()


def test_seeding_is_idempotent_and_never_overwrites_an_admins_label():
    row = CrmChoice.objects.get(kind="status", slug="new_lead")
    row.label = "Fresh"
    row.save()

    ensure_seeded()
    row.refresh_from_db()
    assert row.label == "Fresh"


def test_admin_can_relabel_a_system_status(super_admin):
    row = CrmChoice.objects.get(kind="status", slug="hot_lead")
    res = _admin(super_admin).patch(
        f"{CHOICES}/{row.id}", {"label": "Chase Now", "color": "#ff0000"}, format="json"
    )
    assert res.status_code == 200
    row.refresh_from_db()
    assert row.label == "Chase Now"


def test_a_system_slug_cannot_be_changed(super_admin):
    """Re-slugging would move the label while the logic stayed behind."""
    row = CrmChoice.objects.get(kind="status", slug="converted")
    res = _admin(super_admin).patch(f"{CHOICES}/{row.id}", {"slug": "won"}, format="json")
    assert res.status_code == 400
    assert res.data["error"]["code"] == "SYSTEM_SLUG_IMMUTABLE"


def test_a_system_choice_cannot_be_deleted(super_admin):
    row = CrmChoice.objects.get(kind="status", slug="converted")
    res = _admin(super_admin).delete(f"{CHOICES}/{row.id}")
    assert res.status_code == 409
    assert res.data["error"]["code"] == "SYSTEM_CHOICE_UNDELETABLE"
    assert CrmChoice.objects.filter(pk=row.id).exists()


def test_admin_can_add_and_use_a_custom_status(super_admin, sales):
    res = _admin(super_admin).post(
        CHOICES, {"kind": "status", "slug": "ghosted", "label": "Ghosted"}, format="json"
    )
    assert res.status_code == 201
    assert res.data["is_system"] is False

    lead = Lead.objects.create(**_manual())
    assert (
        _admin(sales).patch(f"{ADMIN}/{lead.id}", {"status": "ghosted"}, format="json").status_code
        == 200
    )


def test_a_custom_choice_cannot_squat_on_a_system_slug(super_admin):
    res = _admin(super_admin).post(
        CHOICES, {"kind": "status", "slug": "converted", "label": "Mine"}, format="json"
    )
    assert res.status_code == 409
    assert res.data["error"]["code"] == "RESERVED_SLUG"


def test_a_custom_choice_in_use_cannot_be_deleted(super_admin):
    choice = CrmChoice.objects.create(kind="status", slug="ghosted", label="Ghosted")
    Lead.objects.create(**_manual(), status="ghosted")

    res = _admin(super_admin).delete(f"{CHOICES}/{choice.id}")
    assert res.status_code == 409
    assert res.data["error"]["code"] == "CHOICE_IN_USE"


def test_an_unused_custom_choice_can_be_deleted(super_admin):
    choice = CrmChoice.objects.create(kind="status", slug="ghosted", label="Ghosted")
    assert _admin(super_admin).delete(f"{CHOICES}/{choice.id}").status_code == 204


def test_an_unknown_status_is_rejected(sales):
    lead = Lead.objects.create(**_manual())
    res = _admin(sales).patch(f"{ADMIN}/{lead.id}", {"status": "invented"}, format="json")
    assert res.status_code == 400


def test_a_deactivated_choice_is_hidden_from_pickers_but_history_survives(sales):
    lead = Lead.objects.create(**_manual(), status="ghosted")
    CrmChoice.objects.create(kind="status", slug="ghosted", label="Ghosted", is_active=False)

    listed = [c["slug"] for c in _admin(sales).get(f"{CHOICES}?kind=status").data]
    assert "ghosted" not in listed
    assert _admin(sales).get(f"{ADMIN}/{lead.id}").data["status"] == "ghosted"


def test_sales_cannot_reconfigure_everyones_dropdowns(sales):
    """Reshaping the CRM's vocabulary is platform config, not a sales action."""
    res = _admin(sales).post(
        CHOICES, {"kind": "status", "slug": "ghosted", "label": "Ghosted"}, format="json"
    )
    assert res.status_code == 403


# ── Admin management ────────────────────────────────────────────────────────
def test_admin_lists_leads(super_admin):
    Lead.objects.create(**VALID)
    res = _admin(super_admin).get(ADMIN)
    assert res.status_code == 200
    assert len(res.data["results"]) == 1
    assert res.data["results"][0]["email"] == "ali@bloomcafe.com"


def test_admin_requires_auth():
    Lead.objects.create(**VALID)
    assert APIClient().get(ADMIN).status_code in (401, 403)


def test_delete_lead_takes_its_history_with_it(super_admin):
    lead = Lead.objects.create(**VALID)
    LeadActivity.objects.create(lead=lead, kind="lead_created", title="x", actor_label="System")
    LeadCall.objects.create(lead=lead, called_at=timezone.now(), result="busy")

    res = _admin(super_admin).delete(f"{ADMIN}/{lead.id}")
    assert res.status_code == 204
    assert Lead.objects.count() == 0
    assert LeadActivity.objects.count() == 0
    assert LeadCall.objects.count() == 0
    assert AdminAuditLog.objects.filter(action="lead.delete").exists()


def test_sales_can_read_the_assignment_picker_without_the_admin_team_api(sales, read_only):
    """The picker must work for Sales, who deliberately lack ADMINS_MANAGE. If
    this ever 403s, the fix is not to widen that permission."""
    assert _admin(sales).get("/api/admin/v1/admins").status_code == 403

    res = _admin(sales).get(f"{ADMIN}/sales-users")
    assert res.status_code == 200
    emails = {a["email"] for a in res.data}
    assert "sales@stampn.net" in emails
    assert "ro@stampn.net" not in emails  # read-only admins are not assignable


def test_the_assignment_picker_leaks_no_security_state(sales):
    row = _admin(sales).get(f"{ADMIN}/sales-users").data[0]
    assert set(row) == {"id", "name", "email", "role"}


def test_a_deactivated_admin_is_not_assignable(sales):
    sales.is_active = False
    sales.save()
    # A deactivated admin cannot authenticate, so ask as someone who can.
    other = AdminUser(email="s2@stampn.net", role=AdminRole.SALES)
    other.set_password("supersecret1")
    other.save()

    emails = {a["email"] for a in _admin(other).get(f"{ADMIN}/sales-users").data}
    assert "sales@stampn.net" not in emails


# ── Merge duplicates ────────────────────────────────────────────────────────
def _dup_pair(sales):
    """A survivor with gaps + an absorbed lead that fills some of them."""
    survivor = Lead.objects.create(
        business_name="Bloom Café", name="Ali", phone="01000000000", status="interested"
    )
    absorbed = Lead.objects.create(
        business_name="Bloom Cafe",  # same name, different casing
        name="Ali Hassan",
        phone="01000000000",
        email="ali@bloom.com",
        area="Zamalek",
        status="new_lead",
    )
    return survivor, absorbed


def test_merge_lists_a_leads_own_duplicates(sales):
    survivor, absorbed = _dup_pair(sales)
    res = _admin(sales).get(f"{ADMIN}/{survivor.id}/duplicates")
    assert res.status_code == 200
    ids = {r["id"] for r in res.data}
    assert str(absorbed.id) in ids
    assert str(survivor.id) not in ids  # never itself


def test_merge_fills_the_survivors_gaps_without_overwriting(sales):
    survivor, absorbed = _dup_pair(sales)
    res = _admin(sales).post(
        f"{ADMIN}/{survivor.id}/merge", {"absorbed_id": str(absorbed.id)}, format="json"
    )
    assert res.status_code == 200

    survivor.refresh_from_db()
    assert survivor.email == "ali@bloom.com"  # gap filled from absorbed
    assert survivor.area == "Zamalek"  # gap filled
    assert survivor.name == "Ali"  # NOT overwritten — survivor had a value
    assert Lead.objects.filter(pk=absorbed.pk).count() == 0  # absorbed is gone


def test_merge_keeps_the_survivors_pipeline_position(sales):
    """A merge must never drag a qualified lead backwards. The survivor was
    Interested; the absorbed one was New Lead — Interested must stand."""
    survivor, absorbed = _dup_pair(sales)
    _admin(sales).post(
        f"{ADMIN}/{survivor.id}/merge", {"absorbed_id": str(absorbed.id)}, format="json"
    )
    survivor.refresh_from_db()
    assert survivor.status == "interested"


def test_merge_moves_calls_and_timeline_across(sales):
    """Nothing that happened is lost when the row goes."""
    survivor, absorbed = _dup_pair(sales)
    LeadCall.objects.create(lead=absorbed, called_at=timezone.now(), result="owner_answered")
    LeadActivity.objects.create(
        lead=absorbed, kind="phone_call_logged", title="Phone Call Logged", actor_label="Nour"
    )

    _admin(sales).post(
        f"{ADMIN}/{survivor.id}/merge", {"absorbed_id": str(absorbed.id)}, format="json"
    )

    assert survivor.calls.count() == 1
    assert survivor.activities.filter(kind="phone_call_logged").exists()
    assert survivor.activities.filter(kind=crm.ActivityKind.DUPLICATE_MERGED).exists()
    # The moved rows are not orphaned or duplicated.
    assert LeadCall.objects.count() == 1


def test_merge_concatenates_both_notes(sales):
    survivor = Lead.objects.create(
        business_name="Bloom", name="Ali", phone="01000000000", notes="Prefers WhatsApp."
    )
    absorbed = Lead.objects.create(
        business_name="Bloom", name="Ali", phone="01000000000", notes="Owner is Ali's brother."
    )
    _admin(sales).post(
        f"{ADMIN}/{survivor.id}/merge", {"absorbed_id": str(absorbed.id)}, format="json"
    )
    survivor.refresh_from_db()
    assert "Prefers WhatsApp." in survivor.notes
    assert "Owner is Ali's brother." in survivor.notes


def test_merge_logs_the_audit_trail(sales):
    survivor, absorbed = _dup_pair(sales)
    _admin(sales).post(
        f"{ADMIN}/{survivor.id}/merge", {"absorbed_id": str(absorbed.id)}, format="json"
    )
    assert AdminAuditLog.objects.filter(action="lead.merge").exists()


def test_a_lead_cannot_be_merged_into_itself(sales):
    survivor, _ = _dup_pair(sales)
    res = _admin(sales).post(
        f"{ADMIN}/{survivor.id}/merge", {"absorbed_id": str(survivor.id)}, format="json"
    )
    assert res.status_code == 409
    assert res.data["error"]["code"] == "SAME_LEAD"


def test_a_converted_lead_cannot_be_absorbed(sales):
    """It is linked to a live merchant — deleting it would strand the merchant's
    origin. Merge the other direction instead."""
    survivor = Lead.objects.create(business_name="Bloom", name="Ali", phone="01000000000")
    absorbed = Lead.objects.create(business_name="Bloom", name="Ali", phone="01000000000")
    # Mark absorbed as converted without needing a real merchant row.
    from core.models import Merchant

    absorbed.converted_merchant = Merchant.objects.create(name="Bloom", slug="bloom-merge-test")
    absorbed.converted_at = timezone.now()
    absorbed.save()

    res = _admin(sales).post(
        f"{ADMIN}/{survivor.id}/merge", {"absorbed_id": str(absorbed.id)}, format="json"
    )
    assert res.status_code == 409
    assert res.data["error"]["code"] == "ABSORBED_CONVERTED"
    assert Lead.objects.filter(pk=absorbed.pk).exists()  # nothing deleted


def test_merge_needs_an_absorbed_id(sales):
    survivor, _ = _dup_pair(sales)
    res = _admin(sales).post(f"{ADMIN}/{survivor.id}/merge", {}, format="json")
    assert res.status_code == 400
    assert res.data["error"]["code"] == "NO_ABSORBED"


def test_read_only_admin_cannot_merge(read_only):
    survivor = Lead.objects.create(business_name="Bloom", name="Ali", phone="01000000000")
    absorbed = Lead.objects.create(business_name="Bloom", name="Ali", phone="01000000000")
    res = _admin(read_only).post(
        f"{ADMIN}/{survivor.id}/merge", {"absorbed_id": str(absorbed.id)}, format="json"
    )
    assert res.status_code == 403
    assert Lead.objects.filter(pk=absorbed.pk).exists()


def test_sales_role_holds_the_crm_permissions_but_not_config():
    from console.rbac import Permission, role_can

    assert role_can(AdminRole.SALES, Permission.LEADS_MANAGE)
    assert role_can(AdminRole.SALES, Permission.LEADS_CONVERT)
    assert not role_can(AdminRole.SALES, Permission.CRM_CONFIGURE)
    assert not role_can(AdminRole.SALES, Permission.BILLING_MANAGE)
