"""Idempotency for mutating loyalty endpoints (stamp / redeem).

A client sends an ``Idempotency-Key`` header (one stable UUID per user action,
reused on retry). The first request claims the key, runs the mutation, and stores
its response; any later request with the same key returns that stored response
without repeating the mutation — so a dropped response + client retry can't
double-stamp. Requests without the header behave exactly as before.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.db import IntegrityError, transaction
from rest_framework.request import Request

from common.errors import Conflict
from core.models import Merchant
from loyalty.models import IdempotencyRecord

HEADER = "Idempotency-Key"


def run_idempotent(
    request: Request,
    *,
    merchant: Merchant,
    endpoint: str,
    mutate: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Run ``mutate`` at most once per ``(merchant, endpoint, Idempotency-Key)``.

    No header → just run ``mutate``. Otherwise claim the key first (so a
    concurrent duplicate can't also mutate), run ``mutate``, and persist its
    response. A replay returns the stored response; an overlapping duplicate that
    finds the key still in flight raises ``Conflict`` (409).
    """
    key = request.headers.get(HEADER, "").strip()
    if not key:
        return mutate()

    try:
        # Independent transaction so the claim commits immediately and the unique
        # constraint blocks any concurrent duplicate.
        with transaction.atomic():
            record = IdempotencyRecord.objects.create(
                merchant=merchant, endpoint=endpoint, key=key, response=None
            )
    except IntegrityError:
        existing = IdempotencyRecord.objects.get(merchant=merchant, endpoint=endpoint, key=key)
        if existing.response is None:
            raise Conflict("A request with this Idempotency-Key is still being processed.")
        return existing.response

    try:
        payload = mutate()
    except BaseException:
        # Mutation failed (e.g. cooldown) — release the claim so a later retry
        # with the same key can try again.
        record.delete()
        raise

    record.response = payload
    record.save(update_fields=["response"])
    return payload
