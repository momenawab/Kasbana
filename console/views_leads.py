"""Admin console views for the lead CRM.

Reads stay open to any active admin (the ``AdminAPIView`` base) — the whole team
benefits from seeing the pipeline. Mutations gate on ``LEADS_MANAGE``, held by
Sales and super-admin (see ``console.rbac``).

Deliberately thin: the pipeline's rules live in ``console.crm_service`` and its
querying in ``console.leads``, so the same invariants hold whether a lead is
touched from here, from the public marketing form, or from a later CSV import.
"""

from __future__ import annotations

import json
from typing import cast

from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from common import uploads
from common.errors import PayloadTooLarge
from common.pagination import DefaultCursorPagination
from console import audit, crm, crm_convert, crm_import, crm_service
from console import leads as lead_query
from console.enums import AdminRole
from console.models import AdminUser, Lead
from console.permissions import AdminAPIView, require
from console.rbac import Permission
from console.serializers_leads import (
    LeadCallCreateSerializer,
    LeadCallSerializer,
    LeadDetailSerializer,
    LeadSerializer,
    LeadWriteSerializer,
)


class _LeadCursorPagination(DefaultCursorPagination):
    """Cursor pagination whose ordering the view sets per request, so a sorted
    table pages by what it displays rather than paging by created_at while
    showing lead score.

    DRF types ``ordering`` as a plain str but accepts a tuple of fields at
    runtime, which is what a sort with a tiebreak needs — hence the re-annotation.
    """

    ordering: tuple[str, ...]  # type: ignore[assignment]

    def __init__(self, ordering: tuple[str, ...]):
        super().__init__()
        self.ordering = ordering


class LeadListView(AdminAPIView):
    """GET /leads — the pipeline (filter/search/sort/paginate) ·
    POST /leads — create a manual lead (Sales+)."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require(Permission.LEADS_MANAGE)()]
        return super().get_permissions()

    @extend_schema(responses=LeadSerializer(many=True))
    def get(self, request: Request) -> Response:
        qs = lead_query.apply_filters(lead_query.lead_queryset(), request.query_params)
        qs, ordering = lead_query.apply_sort(qs, request.query_params)

        paginator = _LeadCursorPagination(ordering)
        page = paginator.paginate_queryset(qs, request, view=self) or []
        return paginator.get_paginated_response(LeadSerializer(page, many=True).data)

    @extend_schema(request=LeadWriteSerializer, responses=LeadDetailSerializer)
    def post(self, request: Request) -> Response:
        serializer = LeadWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Duplicate detection is advisory, and opt-out by design: a shop with two
        # branches legitimately has two leads on one phone number, so the caller
        # decides. The console shows the matches and offers Open / Merge / Create
        # Anyway — ``force=true`` is that third button.
        if str(request.data.get("force", "")).lower() not in ("1", "true"):
            duplicates = crm_service.find_duplicates(
                phone=data.get("phone", ""),
                email=data.get("email", ""),
                business_name=data.get("business_name", ""),
            )
            if duplicates.exists():
                return Response(
                    {
                        "error": {
                            "code": "POSSIBLE_DUPLICATE",
                            "message": (
                                "A lead with this phone, email or business name already exists."
                            ),
                            "duplicates": LeadSerializer(duplicates[:5], many=True).data,
                        }
                    },
                    status=409,
                )

        # Non-null: the LEADS_MANAGE gate above only passes an active AdminUser.
        lead = crm_service.create_manual_lead(actor=cast(AdminUser, request.user), **data)
        audit.record(
            request,
            "lead.create",
            target_type="lead",
            target_id=str(lead.id),
            metadata={"business_name": lead.business_name, "lead_type": lead.lead_type},
        )
        return Response(LeadDetailSerializer(lead).data, status=201)


class LeadKpiView(AdminAPIView):
    """GET /leads/kpis — the dashboard cards.

    Takes the same filter params as the list, so the cards describe the slice
    the user is looking at rather than silently contradicting the table below.
    """

    @extend_schema(responses=None)
    def get(self, request: Request) -> Response:
        qs = lead_query.apply_filters(lead_query.lead_queryset(), request.query_params)
        return Response(lead_query.kpis(qs))


class LeadBulkDeleteView(AdminAPIView):
    """POST /leads/bulk-delete {scope: "all" | "closed"} — purge leads in bulk.

    Super-admin only (``CRM_CONFIGURE``). Deleting a *single* lead is Sales'
    to do (``LEADS_MANAGE``), but emptying the pipeline — or every finished
    lead in it — is a settings-screen hammer held by the same role that
    reshapes the CRM's vocabulary. It is irreversible, so it lives behind the
    same gate as the rest of the destructive config.

    ``closed`` means the pipeline's terminal statuses (Converted, Customer, Not
    Interested, Do Not Call Again, Closed) — the leads the board already treats
    as done. Deleting a converted lead removes only the lead row; the merchant
    it created is a separate record and is untouched.
    """

    permission_classes = [require(Permission.CRM_CONFIGURE)]

    @extend_schema(request=None, responses=None)
    def post(self, request: Request) -> Response:
        scope = (request.data.get("scope") or "").strip()
        qs = Lead.objects.all()
        if scope == "closed":
            qs = qs.filter(status__in=crm.TERMINAL_STATUSES)
        elif scope != "all":
            return Response(
                {"error": {"code": "BAD_SCOPE", "message": "scope must be 'all' or 'closed'."}},
                status=400,
            )

        # Count before the delete — .delete() returns a total across cascaded
        # rows (activities + calls), not the number of leads, which is the only
        # figure that means anything to the person who pressed the button.
        deleted = qs.count()
        qs.delete()  # cascades each lead's timeline and calls
        audit.record(
            request,
            "lead.bulk_delete",
            target_type="lead",
            target_id="",
            metadata={"scope": scope, "deleted": deleted},
        )
        return Response({"deleted": deleted})


class LeadSalesUsersView(AdminAPIView):
    """GET /leads/sales-users — who a lead may be assigned to.

    Exists rather than reusing ``GET /admins`` because that endpoint gates on
    ``ADMINS_MANAGE``, which Sales deliberately does not hold — pointing the
    assignment picker at it would 403 for the very role that lives in this
    screen. Widening that permission to fix a dropdown would hand the sales team
    the admin-team management API, so the CRM gets its own read instead: name
    and email only, no roles, no MFA state, no lockout counters.

    Super-admins are assignable alongside Sales — they hold every permission,
    and a one-person team must still be able to put a lead on someone.
    """

    @extend_schema(responses=None)
    def get(self, request: Request) -> Response:
        assignable = AdminUser.objects.filter(
            is_active=True, role__in=[AdminRole.SALES, AdminRole.SUPER_ADMIN]
        ).order_by("name", "email")
        return Response(
            [
                {"id": str(a.id), "name": a.name, "email": a.email, "role": a.role}
                for a in assignable
            ]
        )


class LeadDuplicateCheckView(AdminAPIView):
    """GET /leads/duplicates?phone=&email=&business_name= — probe before creating.

    Lets the Add Lead form warn as the user types rather than only after they
    submit and get a 409 back.
    """

    @extend_schema(responses=LeadSerializer(many=True))
    def get(self, request: Request) -> Response:
        matches = crm_service.find_duplicates(
            phone=request.query_params.get("phone", "").strip(),
            email=request.query_params.get("email", "").strip(),
            business_name=request.query_params.get("business_name", "").strip(),
            exclude_id=request.query_params.get("exclude") or None,
        )
        return Response(LeadSerializer(matches[:5], many=True).data)


class LeadMergeView(AdminAPIView):
    """GET /leads/{id}/duplicates — this lead's likely duplicates ·
    POST /leads/{id}/merge {absorbed_id} — fold another lead into this one (Sales+).

    The lead in the path is always the survivor: merge happens *from* the record
    you are keeping, absorbing the other into it. That direction is the whole
    reason merge is safe — the survivor's pipeline position and its already-set
    fields are never touched, so a merge cannot quietly downgrade a lead.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [require(Permission.LEADS_MANAGE)()]
        return super().get_permissions()

    @extend_schema(responses=LeadSerializer(many=True))
    def get(self, request: Request, lead_id: str) -> Response:
        lead = get_object_or_404(Lead, pk=lead_id)
        matches = crm_service.find_duplicates(
            phone=lead.phone,
            email=lead.email,
            business_name=lead.business_name,
            exclude_id=lead.id,
        )
        return Response(LeadSerializer(matches[:10], many=True).data)

    @extend_schema(request=None, responses=LeadDetailSerializer)
    def post(self, request: Request, lead_id: str) -> Response:
        survivor = get_object_or_404(Lead, pk=lead_id)
        absorbed_id = (request.data.get("absorbed_id") or "").strip()
        if not absorbed_id:
            return Response(
                {"error": {"code": "NO_ABSORBED", "message": "Choose a lead to merge in."}},
                status=400,
            )
        absorbed = get_object_or_404(Lead, pk=absorbed_id)

        try:
            crm_service.merge_leads(
                survivor=survivor,
                absorbed=absorbed,
                actor=cast(AdminUser, request.user),
            )
        except crm_service.MergeError as exc:
            return Response({"error": {"code": exc.code, "message": exc.message}}, status=409)

        audit.record(
            request,
            "lead.merge",
            target_type="lead",
            target_id=str(survivor.id),
            metadata={
                "absorbed_id": absorbed_id,
                "absorbed_business": absorbed.business_name,
                "survivor_business": survivor.business_name,
            },
        )
        return Response(LeadDetailSerializer(self._reload(survivor.id)).data)

    @staticmethod
    def _reload(lead_id) -> Lead:
        # Re-read so the timeline includes the merge entry and the moved calls.
        return get_object_or_404(
            lead_query.lead_queryset().prefetch_related("activities", "calls"), pk=lead_id
        )


class LeadDetailView(AdminAPIView):
    """GET /leads/{id} — the details page · PATCH — edit (Sales+) · DELETE (Sales+)."""

    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [require(Permission.LEADS_MANAGE)()]
        return super().get_permissions()

    def _lead(self, lead_id: str) -> Lead:
        return get_object_or_404(
            lead_query.lead_queryset().prefetch_related("activities", "calls"), pk=lead_id
        )

    @extend_schema(responses=LeadDetailSerializer)
    def get(self, request: Request, lead_id: str) -> Response:
        return Response(LeadDetailSerializer(self._lead(lead_id)).data)

    @extend_schema(request=LeadWriteSerializer, responses=LeadDetailSerializer)
    def patch(self, request: Request, lead_id: str) -> Response:
        lead = self._lead(lead_id)
        serializer = LeadWriteSerializer(lead, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        crm_service.apply_update(
            lead, serializer.validated_data, actor=cast(AdminUser, request.user)
        )
        audit.record(
            request,
            "lead.update",
            target_type="lead",
            target_id=str(lead.id),
            metadata={"fields": sorted(serializer.validated_data), "status": lead.status},
        )
        # Re-read: apply_update writes activities, so the prefetch on ``lead`` is
        # stale and would return a timeline missing the entry just written.
        return Response(LeadDetailSerializer(self._lead(lead_id)).data)

    @extend_schema(responses=None)
    def delete(self, request: Request, lead_id: str) -> Response:
        lead = get_object_or_404(Lead, pk=lead_id)
        audit.record(
            request,
            "lead.delete",
            target_type="lead",
            target_id=str(lead.id),
            metadata={"business_name": lead.business_name, "email": lead.email},
        )
        lead.delete()  # cascades the timeline and calls — the lead is the record
        return Response(status=204)


class LeadLogoView(AdminAPIView):
    """POST /leads/{id}/logo (multipart) — upload the business logo (Sales+).

    Separate from the merchant dashboard's ``POST /uploads`` because that one
    authenticates a merchant and gates on a merchant role — an admin cannot call
    it at all. What counts as an acceptable image is shared, though
    (``common.uploads``): two auth boundaries, one set of rules.
    """

    permission_classes = [require(Permission.LEADS_MANAGE)]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=None, responses=LeadDetailSerializer)
    def post(self, request: Request, lead_id: str) -> Response:
        lead = get_object_or_404(Lead, pk=lead_id)
        path = uploads.save_image(request.FILES.get("file"), prefix="lead-logos")

        lead.logo_url = uploads.absolute_url(request, path)
        lead.save(update_fields=["logo_url", "updated_at"])
        audit.record(
            request,
            "lead.logo.upload",
            target_type="lead",
            target_id=str(lead.id),
            metadata={"business_name": lead.business_name},
        )
        return Response(LeadDetailSerializer(lead).data)


class LeadImportPreviewView(AdminAPIView):
    """POST /leads/import/preview (multipart) — read the file, propose a mapping.

    Writes nothing. Parsing and importing are separate calls on purpose: a
    mapping guessed wrong and applied silently would load phone numbers into
    four hundred leads' area field, and nobody would notice until they called
    one. The human confirms the mapping in between.
    """

    permission_classes = [require(Permission.LEADS_MANAGE)]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=None, responses=None)
    def post(self, request: Request) -> Response:
        file_obj = request.FILES.get("file")
        if file_obj is not None and file_obj.size > settings.UPLOAD_MAX_SIZE_BYTES:
            # The same ceiling as image uploads. A spreadsheet past it is one
            # that should be split — and openpyxl on an unbounded file is how a
            # zip bomb becomes an outage.
            raise PayloadTooLarge()
        try:
            data = crm_import.preview(file_obj)
            # Answering "how many of these do we already have?" before the human
            # commits is the difference between a useful preview and a shrug.
            columns, rows = crm_import.parse_upload(_rewound(file_obj))
            data["existing_matches"] = crm_import.existing_phone_count(
                rows, data["suggested_mapping"]
            )
        except crm_import.ImportError_ as exc:
            return Response({"error": {"code": exc.code, "message": exc.message}}, status=400)
        return Response(data)


class LeadImportView(AdminAPIView):
    """POST /leads/import (multipart: file + mapping JSON) — create the leads.

    The file is uploaded again rather than parked on the server between the two
    calls: the browser already holds it, and a temp file keyed to a session is
    state to expire, clean up and leak. Re-parsing a 5,000-row sheet is cheap by
    comparison.
    """

    permission_classes = [require(Permission.LEADS_MANAGE)]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=None, responses=None)
    def post(self, request: Request) -> Response:
        file_obj = request.FILES.get("file")
        if file_obj is not None and file_obj.size > settings.UPLOAD_MAX_SIZE_BYTES:
            raise PayloadTooLarge()

        try:
            mapping = json.loads(request.data.get("mapping") or "{}")
        except json.JSONDecodeError:
            return Response(
                {"error": {"code": "BAD_MAPPING", "message": "Mapping is not valid JSON."}},
                status=400,
            )
        if not isinstance(mapping, dict):
            return Response(
                {"error": {"code": "BAD_MAPPING", "message": "Mapping must be an object."}},
                status=400,
            )

        assigned = None
        if assigned_id := (request.data.get("assigned_sales") or "").strip():
            assigned = get_object_or_404(AdminUser, pk=assigned_id, is_active=True)

        source = (request.data.get("source") or crm.LeadSource.OTHER).strip()

        try:
            _, rows = crm_import.parse_upload(_rewound(file_obj))
            summary = crm_import.import_rows(
                rows,
                mapping,
                actor=cast(AdminUser, request.user),
                source=source,
                assigned_sales=assigned,
                skip_duplicates=str(request.data.get("skip_duplicates", "true")).lower()
                not in ("0", "false"),
            )
        except crm_import.ImportError_ as exc:
            return Response({"error": {"code": exc.code, "message": exc.message}}, status=400)

        audit.record(
            request,
            "lead.import",
            target_type="lead",
            target_id="",
            metadata={
                "created": summary["created"],
                "skipped": summary["skipped"],
                "failed": summary["failed"],
                "file": getattr(file_obj, "name", ""),
            },
        )
        return Response(summary, status=201)


def _rewound(file_obj):
    """A file handle back at byte zero.

    Django's uploaded files are read once by ``preview`` and again for the row
    data; without this the second read gets an empty string and reports a file
    with no rows, which is a confusing way to say "already consumed".
    """
    if file_obj is not None and hasattr(file_obj, "seek"):
        file_obj.seek(0)
    return file_obj


class LeadConvertView(AdminAPIView):
    """POST /leads/{id}/convert {plan_key} — turn the lead into a live merchant.

    Gated on ``LEADS_CONVERT`` rather than ``LEADS_MANAGE``: this is the one
    lead action that reaches outside the CRM and creates real, billable
    accounts, so it is worth being able to grant separately from day-to-day
    pipeline work.
    """

    permission_classes = [require(Permission.LEADS_CONVERT)]

    @extend_schema(request=None, responses=LeadDetailSerializer)
    def post(self, request: Request, lead_id: str) -> Response:
        lead = get_object_or_404(Lead, pk=lead_id)
        try:
            result = crm_convert.convert_lead(
                lead,
                actor=cast(AdminUser, request.user),
                plan_key=(request.data.get("plan_key") or "").strip(),
            )
        except crm_convert.ConversionError as exc:
            # The service knows why a conversion cannot proceed and says so in
            # sales' language; the view just picks the status code.
            status_code = 409 if exc.code != "UNKNOWN_PLAN" else 400
            return Response(
                {"error": {"code": exc.code, "message": exc.message}}, status=status_code
            )

        merchant = result["merchant"]
        audit.record(
            request,
            "lead.convert",
            target_type="lead",
            target_id=str(lead.id),
            metadata={
                "merchant_id": str(merchant.id),
                "merchant_name": merchant.name,
                "plan": result["subscription"].plan,
                "email_sent": result["email_sent"],
            },
        )
        return Response(
            {
                "lead": LeadDetailSerializer(lead).data,
                "merchant": {
                    "id": str(merchant.id),
                    "name": merchant.name,
                    "slug": merchant.slug,
                    "plan": result["subscription"].plan,
                },
                # False means the account exists but its owner was never told.
                # Sales needs to know that at the moment of conversion, not when
                # the merchant calls a week later asking why nothing arrived.
                "email_sent": result["email_sent"],
            },
            status=201,
        )


class LeadCallView(AdminAPIView):
    """POST /leads/{id}/calls — Log Call (Sales+).

    Logging a call does four things at once, which is why it is not a plain
    create: it records the call, moves the lead's follow-up date, stamps
    ``last_contact_at``, and lands on the timeline.
    """

    permission_classes = [require(Permission.LEADS_MANAGE)]

    @extend_schema(request=LeadCallCreateSerializer, responses=LeadCallSerializer)
    def post(self, request: Request, lead_id: str) -> Response:
        lead = get_object_or_404(Lead, pk=lead_id)
        serializer = LeadCallCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        actor = cast(AdminUser, request.user)  # non-null: LEADS_MANAGE passed
        call = serializer.save(
            lead=lead,
            logged_by=actor,
            logged_by_label=actor.name or actor.email,
        )

        updates = ["last_contact_at", "updated_at"]
        lead.last_contact_at = call.called_at
        if lead.contacted_at is None:
            lead.contacted_at = call.called_at
            updates.append("contacted_at")
        if call.next_follow_up_at:
            lead.next_follow_up_at = call.next_follow_up_at
            updates.append("next_follow_up_at")
        lead.save(update_fields=updates)

        minutes = round(call.duration_seconds / 60)
        crm_service.log_activity(
            lead,
            crm.ActivityKind.PHONE_CALL_LOGGED,
            "Phone Call Logged",
            description=(
                f"{crm.CallResult(call.result).label} · {minutes} min"
                + (f" — {call.notes}" if call.notes else "")
            ),
            actor=actor,
        )
        audit.record(
            request,
            "lead.call.log",
            target_type="lead",
            target_id=str(lead.id),
            metadata={"result": call.result, "duration_seconds": call.duration_seconds},
        )
        return Response(LeadCallSerializer(call).data, status=201)
