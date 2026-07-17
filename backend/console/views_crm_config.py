"""Settings → CRM Configuration — the console's editable dropdowns.

Every CRM picker reads from here rather than hardcoding its values. What an
admin may do to a row depends on who owns the slug:

* ``is_system=True`` — the value exists in ``console.crm`` and code reads it by
  name. Label, colour and order are the admin's; the slug and the row's
  existence are not. Deleting one would not just remove an option, it would
  strand every lead already sitting on it and break the scoring and conversion
  that key off it, so the delete is refused rather than cascaded.
* ``is_system=False`` — admin-invented vocabulary that no code reads. Fully
  theirs, including delete.

Deactivating (``is_active=False``) is the escape hatch for both: it hides a
value from new pickers while leaving the leads already on it readable. That is
almost always what "remove this status" actually means.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from console import audit, crm
from console.models import CrmChoice, Lead
from console.permissions import AdminAPIView, require
from console.rbac import Permission
from console.serializers_leads import CrmChoiceSerializer


class CrmChoiceListView(AdminAPIView):
    """GET /crm/choices[?kind=] — every configurable value (any admin, since
    every CRM picker needs them) · POST — add a custom value (super-admin)."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require(Permission.CRM_CONFIGURE)()]
        return super().get_permissions()

    @extend_schema(responses=CrmChoiceSerializer(many=True))
    def get(self, request: Request) -> Response:
        qs = CrmChoice.objects.all()
        if kind := request.query_params.get("kind", "").strip():
            qs = qs.filter(kind=kind)
        # Pickers want only what can still be chosen; the settings page wants
        # everything, including what has been retired.
        if request.query_params.get("include_inactive") not in ("1", "true"):
            qs = qs.filter(is_active=True)
        return Response(CrmChoiceSerializer(qs, many=True).data)

    @extend_schema(request=CrmChoiceSerializer, responses=CrmChoiceSerializer)
    def post(self, request: Request) -> Response:
        serializer = CrmChoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kind = serializer.validated_data["kind"]
        slug = serializer.validated_data["slug"]

        # A custom row may not squat on a system slug: the code would read the
        # slug and get the enum's meaning, while the settings page showed the
        # admin's — two truths for one value.
        if crm.is_system_value(kind, slug):
            return Response(
                {
                    "error": {
                        "code": "RESERVED_SLUG",
                        "message": (
                            f"'{slug}' is a built-in {kind} — edit the existing row instead."
                        ),
                    }
                },
                status=409,
            )
        if CrmChoice.objects.filter(kind=kind, slug=slug).exists():
            return Response(
                {"error": {"code": "DUPLICATE_SLUG", "message": f"'{slug}' already exists."}},
                status=409,
            )

        choice = serializer.save(is_system=False)
        audit.record(
            request,
            "crm_choice.create",
            target_type="crm_choice",
            target_id=str(choice.id),
            metadata={"kind": choice.kind, "slug": choice.slug},
        )
        return Response(CrmChoiceSerializer(choice).data, status=201)


class CrmChoiceDetailView(AdminAPIView):
    """PATCH /crm/choices/{id} — relabel/recolour/reorder · DELETE — remove a
    custom value. Both super-admin (``CRM_CONFIGURE``)."""

    permission_classes = [require(Permission.CRM_CONFIGURE)]

    @extend_schema(request=CrmChoiceSerializer, responses=CrmChoiceSerializer)
    def patch(self, request: Request, choice_id: str) -> Response:
        choice = get_object_or_404(CrmChoice, pk=choice_id)
        serializer = CrmChoiceSerializer(choice, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Re-slugging a system row would silently detach it from the enum the
        # code reads: the label would move, the logic would not follow.
        new_slug = serializer.validated_data.get("slug")
        if choice.is_system and new_slug and new_slug != choice.slug:
            return Response(
                {
                    "error": {
                        "code": "SYSTEM_SLUG_IMMUTABLE",
                        "message": (
                            "A built-in value's slug is fixed. Change its label instead — "
                            "that is what the console displays."
                        ),
                    }
                },
                status=400,
            )
        if choice.is_system and serializer.validated_data.get("kind", choice.kind) != choice.kind:
            return Response(
                {
                    "error": {
                        "code": "SYSTEM_KIND_IMMUTABLE",
                        "message": "A built-in value cannot move to another dropdown.",
                    }
                },
                status=400,
            )

        choice = serializer.save()
        audit.record(
            request,
            "crm_choice.update",
            target_type="crm_choice",
            target_id=str(choice.id),
            metadata={"kind": choice.kind, "slug": choice.slug, "label": choice.label},
        )
        return Response(CrmChoiceSerializer(choice).data)

    @extend_schema(responses=None)
    def delete(self, request: Request, choice_id: str) -> Response:
        choice = get_object_or_404(CrmChoice, pk=choice_id)

        if choice.is_system:
            return Response(
                {
                    "error": {
                        "code": "SYSTEM_CHOICE_UNDELETABLE",
                        "message": (
                            "A built-in value cannot be deleted — the CRM reads it by name. "
                            "Deactivate it instead to hide it from new leads."
                        ),
                    }
                },
                status=409,
            )

        # A custom value that leads are sitting on is not free to delete either:
        # the lead stores the slug, so removing the row would leave those leads
        # displaying a raw slug with no label. Deactivating keeps them readable.
        in_use = _leads_using(choice)
        if in_use:
            return Response(
                {
                    "error": {
                        "code": "CHOICE_IN_USE",
                        "message": (
                            f"{in_use} lead(s) still use this value. "
                            "Deactivate it to retire it without breaking them."
                        ),
                        "leads_using": in_use,
                    }
                },
                status=409,
            )

        audit.record(
            request,
            "crm_choice.delete",
            target_type="crm_choice",
            target_id=str(choice.id),
            metadata={"kind": choice.kind, "slug": choice.slug},
        )
        choice.delete()
        return Response(status=204)


# Which lead column stores each kind's slug. A kind absent here is one no lead
# references, so nothing can be using it.
_KIND_TO_LEAD_FIELD: dict[str, str] = {
    crm.CrmChoiceKind.STATUS: "status",
    crm.CrmChoiceKind.PRIORITY: "priority",
    crm.CrmChoiceKind.TEMPERATURE: "temperature",
    crm.CrmChoiceKind.SOURCE: "source",
    crm.CrmChoiceKind.CATEGORY: "category",
    crm.CrmChoiceKind.EXPECTED_PLAN: "expected_plan",
    crm.CrmChoiceKind.CONTACT_METHOD: "contact_method",
    crm.CrmChoiceKind.NEXT_ACTION: "next_action",
}


def _leads_using(choice: CrmChoice) -> int:
    field = _KIND_TO_LEAD_FIELD.get(choice.kind)
    if not field:
        return 0
    return Lead.objects.filter(**{field: choice.slug}).count()
