"""Serializers for the lead CRM.

Three read shapes, deliberately: ``LeadSerializer`` is the table row (wide, but
nothing that costs a per-row query), ``LeadDetailSerializer`` adds the timeline
and calls, and ``LeadCreateSerializer`` is the *public* write shape from the
marketing site. The public one stays separate and minimal on purpose — the
marketing form must never be able to set an owner, a score, or a status.

Choice validation goes through ``_ChoiceField``, which checks a value against
the system enum *and* whatever admins have added in ``CrmChoice``. Doing it in
one place is what lets the two coexist: DRF's own ``ChoiceField`` freezes the
valid set at import time, which would silently reject a status an admin added
five minutes ago.
"""

from __future__ import annotations

from rest_framework import serializers

from console import crm
from console.models import AdminUser, CrmChoice, Lead, LeadActivity, LeadCall


class _ChoiceField(serializers.CharField):
    """A CRM dropdown value: a system enum value, or an active admin-added row
    of the same kind. Queries ``CrmChoice`` per validation rather than caching —
    correctness over a query here, since admins edit these live and a stale
    cache would reject a value the settings page is actively offering."""

    def __init__(self, kind: str, **kwargs):
        self.kind = kind
        kwargs.setdefault("allow_blank", True)
        super().__init__(**kwargs)

    def run_validation(self, data=serializers.empty):
        value = super().run_validation(data)
        if not value:
            return value
        if crm.is_system_value(self.kind, value):
            return value
        if CrmChoice.objects.filter(kind=self.kind, slug=value, is_active=True).exists():
            return value
        raise serializers.ValidationError(
            f"'{value}' is not a valid {self.kind}. Add it in Settings → CRM Configuration first."
        )


class LeadCreateSerializer(serializers.ModelSerializer):
    """Public write shape — what the marketing "Get started" form POSTs.

    ``botcheck`` is a honeypot: a real person leaves it empty; a bot that fills
    it is rejected quietly by the view. Email is required here even though the
    model now allows blank, because the marketing form asks for it and a website
    lead with no reply address is a dead one. Manual leads carry no such rule —
    which is exactly why the rule lives here and not on the model.
    """

    botcheck = serializers.CharField(required=False, allow_blank=True, write_only=True)
    email = serializers.EmailField(required=True, allow_blank=False)

    class Meta:
        model = Lead
        fields = ["name", "email", "phone", "business_name", "botcheck"]

    def create(self, validated_data):
        from console import crm_service

        validated_data.pop("botcheck", None)
        return crm_service.create_website_lead(**validated_data)


class LeadWriteSerializer(serializers.ModelSerializer):
    """Console write shape — manual create and edit.

    Provenance (``lead_type``, ``created_by``, ``created_by_type``) is absent by
    design: it is the system's to decide from *how* a lead arrived, never the
    client's to claim. Same for ``lead_score`` and ``last_activity``, which are
    derived — accepting either would let a caller assert a score that the next
    recalculation silently contradicts.
    """

    status = _ChoiceField(crm.CrmChoiceKind.STATUS, required=False)
    priority = _ChoiceField(crm.CrmChoiceKind.PRIORITY, required=False)
    temperature = _ChoiceField(crm.CrmChoiceKind.TEMPERATURE, required=False)
    # ``source`` shadows DRF ``Field.source``'s annotation, so mypy objects; at
    # runtime the metaclass pops declared fields off the class before that
    # attribute is ever read, so the lead's own source field wins as intended.
    source = _ChoiceField(crm.CrmChoiceKind.SOURCE, required=False)  # type: ignore[assignment]
    # Optional here even though the model field is not blank-able: a manual lead
    # is often a business name and a phone number off the street, with the owner's
    # name still unknown. Same split as ``email`` — the model stays permissive and
    # the rule lives in whichever serializer actually needs it.
    name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    category = _ChoiceField(crm.CrmChoiceKind.CATEGORY, required=False)
    expected_plan = _ChoiceField(crm.CrmChoiceKind.EXPECTED_PLAN, required=False)
    contact_method = _ChoiceField(crm.CrmChoiceKind.CONTACT_METHOD, required=False)
    next_action = _ChoiceField(crm.CrmChoiceKind.NEXT_ACTION, required=False)
    assigned_sales = serializers.PrimaryKeyRelatedField(
        queryset=AdminUser.objects.filter(is_active=True), required=False, allow_null=True
    )

    class Meta:
        model = Lead
        fields = [
            "business_name",
            "name",
            "phone",
            "whatsapp",
            "email",
            "instagram",
            "facebook",
            "website",
            "google_maps_url",
            "area",
            "category",
            "address",
            "notes",
            "source",
            "assigned_sales",
            "status",
            "priority",
            "temperature",
            "expected_plan",
            "expected_revenue",
            "contact_method",
            "next_action",
            "last_contact_at",
            "next_follow_up_at",
        ]


class LeadActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadActivity
        fields = ["id", "kind", "title", "description", "actor_label", "created_at"]
        read_only_fields = fields


class LeadCallSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadCall
        fields = [
            "id",
            "called_at",
            "duration_seconds",
            "result",
            "contact_method",
            "next_follow_up_at",
            "notes",
            "logged_by_label",
            "created_at",
        ]
        read_only_fields = fields


class LeadCallCreateSerializer(serializers.ModelSerializer):
    """Log Call. ``next_follow_up_at`` is copied onto the lead by the view — the
    point of setting it here is that the pipeline picks it up."""

    contact_method = _ChoiceField(crm.CrmChoiceKind.CONTACT_METHOD, required=False)
    result = serializers.ChoiceField(choices=crm.CallResult.choices)

    class Meta:
        model = LeadCall
        fields = [
            "called_at",
            "duration_seconds",
            "result",
            "contact_method",
            "next_follow_up_at",
            "notes",
        ]


class _AdminBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminUser
        fields = ["id", "name", "email"]
        read_only_fields = fields


class LeadSerializer(serializers.ModelSerializer):
    """The table row — every column the leads table renders."""

    assigned_sales = _AdminBriefSerializer(read_only=True)
    created_by = _AdminBriefSerializer(read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id",
            "business_name",
            "name",
            "phone",
            "whatsapp",
            "email",
            "area",
            "category",
            "assigned_sales",
            "priority",
            "status",
            "temperature",
            "lead_score",
            "lead_type",
            "source",
            "next_follow_up_at",
            "last_activity",
            "last_contact_at",
            "created_by",
            "created_by_type",
            "created_at",
            "is_converted",
        ]
        read_only_fields = fields


class LeadDetailSerializer(LeadSerializer):
    """The details page: everything, plus the timeline and the calls."""

    activities = LeadActivitySerializer(many=True, read_only=True)
    calls = LeadCallSerializer(many=True, read_only=True)

    class Meta(LeadSerializer.Meta):
        fields = LeadSerializer.Meta.fields + [
            "instagram",
            "facebook",
            "website",
            "google_maps_url",
            "logo_url",
            "address",
            "notes",
            "expected_plan",
            "expected_revenue",
            "contact_method",
            "next_action",
            "contacted_at",
            "converted_merchant",
            "converted_at",
            "updated_at",
            "activities",
            "calls",
        ]
        read_only_fields = fields


class CrmChoiceSerializer(serializers.ModelSerializer):
    """A configurable dropdown row. ``is_system`` is the code's claim on a slug,
    never the client's to set.

    ``validators = []`` drops DRF's implicit unique-together check on
    (kind, slug). Not to weaken it — the database constraint still holds, and
    ``views_crm_config`` re-checks — but because that validator answers a
    collision with a bare "must be unique" 400, which cannot distinguish "you
    already added this" from "this is a built-in you may not shadow". Those need
    different fixes, so the view owns the check and says which one it is.
    """

    class Meta:
        model = CrmChoice
        fields = ["id", "kind", "slug", "label", "color", "order", "is_system", "is_active"]
        read_only_fields = ["id", "is_system"]
        validators: list = []
