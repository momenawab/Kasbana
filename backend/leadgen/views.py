"""Console API for lead generation, mounted under ``/api/admin/v1/leadgen/``.

Thin by design: the rules live in ``leadgen.services``, so a job means the same
thing whether it was started from here, from a retry, or from a test.

Reads are open to any active admin — the whole team benefits from seeing what
the pipeline found. Mutations split into two gates: ``LEADGEN_RUN`` to start or
control a job (which spends real money on Places calls) and ``LEADGEN_IMPORT``
to push a lead into the CRM. Looking is free; billing and writing are not.
"""

from __future__ import annotations

from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from common.pagination import DefaultCursorPagination
from console import audit
from console.models import AdminUser
from console.permissions import AdminAPIView, require
from console.rbac import Permission
from leadgen import enums, serializers
from leadgen.models import GeneratedLead, SearchJob
from leadgen.services import importer
from leadgen.services import jobs as job_service
from leadgen.tasks import enqueue


class _LeadPagination(DefaultCursorPagination):
    ordering = ("-fit_score", "-created_at")


# ── Search jobs ──────────────────────────────────────────────────────────────
class SearchJobListView(AdminAPIView):
    """GET the job list · POST to create and queue a new search."""

    @extend_schema(responses=serializers.SearchJobSerializer(many=True))
    def get(self, request: Request) -> Response:
        queryset = SearchJob.objects.select_related("created_by").all()

        job_status = request.query_params.get("status")
        if job_status:
            queryset = queryset.filter(status=job_status)

        paginator = DefaultCursorPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(
            serializers.SearchJobSerializer(page, many=True).data
        )

    def get_permissions(self):
        if self.request.method == "POST":
            return [require(Permission.LEADGEN_RUN)()]
        return super().get_permissions()

    @extend_schema(
        request=serializers.SearchJobCreateSerializer,
        responses=serializers.SearchJobSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = serializers.SearchJobCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        try:
            job = job_service.create(created_by=request.user, **payload.validated_data)
        except job_service.JobError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Audited because it costs money: a search job is the one console action
        # that bills a third party per call.
        audit.record(
            request,
            action="leadgen.job.created",
            target_id=str(job.id),
            metadata={
                "city": job.city,
                "types": job.business_types,
                "max_results": job.max_results,
            },
        )

        dispatch = enqueue(job)
        job.refresh_from_db()
        return Response(
            {**serializers.SearchJobSerializer(job).data, "dispatch": dispatch},
            status=status.HTTP_201_CREATED,
        )


class SearchJobDetailView(AdminAPIView):
    @extend_schema(responses=serializers.SearchJobSerializer)
    def get(self, request: Request, job_id) -> Response:
        job = get_object_or_404(SearchJob.objects.select_related("created_by"), pk=job_id)
        return Response(serializers.SearchJobSerializer(job).data)


class SearchJobActionView(AdminAPIView):
    """POST pause / resume / cancel / retry.

    One endpoint rather than four: they are the same decision (change this
    job's lifecycle state) and the service owns which transitions are legal, so
    four near-identical views would only duplicate the error handling.
    """

    ACTIONS = {
        "pause": job_service.pause,
        "resume": job_service.resume,
        "cancel": job_service.cancel,
        "retry": job_service.retry,
    }

    def get_permissions(self):
        return [require(Permission.LEADGEN_RUN)()]

    # Named explicitly: drf-spectacular derives operationIds from the path, and
    # this route's trailing ``{action}`` collides with job creation, leaving the
    # generated client with a "…_create_2" method nobody can guess.
    @extend_schema(
        operation_id="leadgen_job_action",
        request=None,
        responses=serializers.SearchJobSerializer,
    )
    def post(self, request: Request, job_id, action: str) -> Response:
        handler = self.ACTIONS.get(action)
        if handler is None:
            return Response(
                {"detail": f"Unknown action “{action}”."}, status=status.HTTP_400_BAD_REQUEST
            )

        job = get_object_or_404(SearchJob, pk=job_id)
        try:
            handler(job)
        except job_service.JobError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        audit.record(request, action=f"leadgen.job.{action}", target_id=str(job.id))

        # Resume and retry both leave the job queued; something has to pick it
        # up again, and the operator expects it to move without a second click.
        if action in ("resume", "retry"):
            enqueue(job)
            job.refresh_from_db()

        return Response(serializers.SearchJobSerializer(job).data)


class SearchJobLogView(AdminAPIView):
    """The operator log — what the pipeline did, and why it stalled."""

    @extend_schema(responses=serializers.JobLogSerializer(many=True))
    def get(self, request: Request, job_id) -> Response:
        job = get_object_or_404(SearchJob, pk=job_id)
        logs = job.logs.all()

        level = request.query_params.get("level")
        if level:
            logs = logs.filter(level=level)

        paginator = DefaultCursorPagination()
        page = paginator.paginate_queryset(logs, request, view=self)
        return paginator.get_paginated_response(
            serializers.JobLogSerializer(page, many=True).data
        )


# ── Generated leads ──────────────────────────────────────────────────────────
class GeneratedLeadListView(AdminAPIView):
    """The results table, with the spec's filters.

    Duplicates are hidden unless asked for. A collapsed branch is not a separate
    prospect, and showing it would make a chain look like five opportunities.
    """

    @extend_schema(responses=serializers.GeneratedLeadListSerializer(many=True))
    def get(self, request: Request) -> Response:
        queryset = (
            GeneratedLead.objects.select_related("website_profile", "job")
            .prefetch_related("socials")
            .all()
        )
        queryset = self._filter(queryset, request)

        paginator = _LeadPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(
            serializers.GeneratedLeadListSerializer(page, many=True).data
        )

    def _filter(self, queryset, request: Request):
        params = request.query_params

        if params.get("job_id"):
            queryset = queryset.filter(job_id=params["job_id"])
        if not _flag(params, "include_duplicates"):
            queryset = queryset.filter(duplicate_of__isnull=True)

        for field, param in (
            ("state", "state"),
            ("score_label", "score_label"),
            ("category", "category"),
            ("job__city", "city"),
            ("job__province", "province"),
        ):
            if params.get(param):
                queryset = queryset.filter(**{field: params[param]})

        if params.get("min_score"):
            queryset = queryset.filter(fit_score__gte=params["min_score"])
        if params.get("max_score"):
            queryset = queryset.filter(fit_score__lte=params["max_score"])
        if params.get("min_rating"):
            queryset = queryset.filter(rating__gte=params["min_rating"])
        if params.get("min_reviews"):
            queryset = queryset.filter(reviews_count__gte=params["min_reviews"])
        if params.get("min_branches"):
            queryset = queryset.filter(branch_count__gte=params["min_branches"])

        # Presence filters. ``website_profile__emails`` cannot be tested for
        # emptiness portably across backends, so an email filter excludes the
        # empty list explicitly rather than relying on truthiness.
        if _flag(params, "has_website"):
            queryset = queryset.exclude(website_domain="")
        if _flag(params, "has_email"):
            queryset = queryset.filter(website_profile__isnull=False).exclude(
                website_profile__emails=[]
            )
        if _flag(params, "has_owner"):
            queryset = queryset.exclude(owner_name="")
        for platform, param in (
            (enums.SocialPlatform.INSTAGRAM, "has_instagram"),
            (enums.SocialPlatform.FACEBOOK, "has_facebook"),
        ):
            if _flag(params, param):
                queryset = queryset.filter(socials__platform=platform)

        if _flag(params, "not_imported"):
            queryset = queryset.filter(imported_lead__isnull=True)

        search = params.get("q")
        if search:
            queryset = queryset.filter(
                Q(business_name__icontains=search)
                | Q(address__icontains=search)
                | Q(phone__icontains=search)
                | Q(website_domain__icontains=search)
            )

        return queryset.distinct()


class GeneratedLeadDetailView(AdminAPIView):
    @extend_schema(responses=serializers.GeneratedLeadDetailSerializer)
    def get(self, request: Request, lead_id) -> Response:
        lead = get_object_or_404(
            GeneratedLead.objects.select_related("website_profile", "job")
            .prefetch_related("socials", "owner_candidates"),
            pk=lead_id,
        )
        return Response(serializers.GeneratedLeadDetailSerializer(lead).data)


class GeneratedLeadOwnerView(AdminAPIView):
    """POST an owner name a rep established themselves.

    Deliberately a manual endpoint. Automated owner discovery is limited to what
    a business publishes about itself; anything a rep learns by other means —
    a phone call, a conversation, a tool on their own device — reaches the
    record through here, and outranks every automated candidate.
    """

    def get_permissions(self):
        return [require(Permission.LEADS_MANAGE)()]

    @extend_schema(
        request=serializers.OwnerNameSerializer,
        responses=serializers.GeneratedLeadDetailSerializer,
    )
    def post(self, request: Request, lead_id) -> Response:
        payload = serializers.OwnerNameSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        lead = get_object_or_404(GeneratedLead, pk=lead_id)
        actor = request.user
        lead.owner_candidates.filter(source=enums.OwnerNameSource.MANUAL).delete()
        lead.owner_candidates.create(
            name=data["name"],
            role=data.get("role", ""),
            source=enums.OwnerNameSource.MANUAL,
            confidence=enums.Confidence.HIGH,
            evidence_text=data.get("note", "") or f"Entered by {actor.name or actor.email}",
        )
        lead.owner_name = data["name"]
        lead.owner_name_source = enums.OwnerNameSource.MANUAL
        lead.owner_name_confidence = enums.Confidence.HIGH
        lead.save(
            update_fields=[
                "owner_name", "owner_name_source", "owner_name_confidence", "updated_at"
            ]
        )

        return Response(serializers.GeneratedLeadDetailSerializer(lead).data)


class GeneratedLeadImportView(AdminAPIView):
    """POST to push one or many generated leads into the CRM."""

    def get_permissions(self):
        return [require(Permission.LEADGEN_IMPORT)()]

    @extend_schema(
        request=serializers.ImportSerializer,
        responses=serializers.ImportResultSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = serializers.ImportSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        leads = list(
            GeneratedLead.objects.select_related("website_profile", "job")
            .prefetch_related("socials")
            .filter(id__in=data["lead_ids"])
        )
        if not leads:
            return Response(
                {"detail": "No matching leads."}, status=status.HTTP_404_NOT_FOUND
            )

        assigned = None
        if data.get("assigned_sales_id"):
            assigned = get_object_or_404(AdminUser, pk=data["assigned_sales_id"])

        created, failed = importer.import_many(
            leads, actor=request.user, assigned_sales=assigned, force=data["force"]
        )

        audit.record(
            request,
            action="leadgen.import",
            metadata={"imported": len(created), "skipped": len(failed)},
        )

        return Response(
            {
                "imported": len(created),
                "crm_lead_ids": [str(lead.id) for lead in created],
                # Per-lead reasons rather than a single failure: a bulk import
                # of fifty where one is a duplicate should tell the operator
                # which one, not refuse the batch.
                "skipped": [
                    {"lead_id": str(lead.id), "business_name": lead.business_name, "reason": why}
                    for lead, why in failed
                ],
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_409_CONFLICT,
        )


def _flag(params, name: str) -> bool:
    return params.get(name, "").lower() in {"1", "true", "yes"}
