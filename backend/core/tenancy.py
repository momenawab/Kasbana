"""Tenant scoping (contract: ``core/`` owns tenancy).

Multi-tenancy key: every tenant-owned row carries a ``merchant`` FK. Use
``Model.objects.for_merchant(merchant)`` to scope a queryset, or ``get_scoped``
in views to fetch one object inside the request's merchant — never trust a raw
PK from the client across tenants.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from django.db import models
from django.shortcuts import get_object_or_404

if TYPE_CHECKING:
    from rest_framework.request import Request

M = TypeVar("M", bound=models.Model)


class TenantQuerySet(models.QuerySet):
    """Queryset for models that carry a direct ``merchant`` FK."""

    def for_merchant(self, merchant: Any) -> TenantQuerySet:
        return self.filter(merchant=merchant)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):  # type: ignore[misc]
    """Default manager for tenant-scoped models."""


def get_request_merchant(request: Request) -> Any:
    """Return the merchant bound to the authenticated request, or ``None``."""
    staff = getattr(request, "staff", None)
    return getattr(staff, "merchant", None) if staff else None


def get_scoped(model: type[M], request: Request, **kwargs: Any) -> M:
    """Fetch one ``model`` instance scoped to the request's merchant.

    Raises 404 (rendered as ``NOT_FOUND``) if it does not exist *within* the
    caller's merchant — so cross-tenant IDs are indistinguishable from missing.
    """
    merchant = get_request_merchant(request)
    return get_object_or_404(model, merchant=merchant, **kwargs)
