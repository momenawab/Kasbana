"""Short human-typeable pass codes (note 1).

Every customer pass shows a short code as the barcode ``altText`` (the text under
the QR). A cashier can type it on the Scan screen instead of scanning. Codes are
generated lazily the first time a pass is built and resolved back — tenant-scoped
— by the Scan endpoint.
"""

from __future__ import annotations

import secrets

from django.db import IntegrityError, transaction

from core.models import CustomerCard
from wallets.models import CardShortCode

# Crockford-ish alphabet: no 0/O/1/I/L to avoid read/type ambiguity.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_LENGTH = 6


def _random_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))


def code_for(customer_card: CustomerCard) -> str:
    """Return the card's short code, creating it on first use.

    Idempotent and race-safe: a concurrent create loses the ``unique`` race and
    re-reads the winning row. Retries on the (astronomically rare) code clash.
    """
    existing = CardShortCode.objects.filter(customer_card=customer_card).first()
    if existing is not None:
        return existing.code

    for _ in range(8):
        code = _random_code()
        try:
            with transaction.atomic():
                row = CardShortCode.objects.create(
                    customer_card=customer_card,
                    merchant=customer_card.merchant,
                    code=code,
                )
            return row.code
        except IntegrityError:
            # Either the code collided (retry) or another request created the
            # row for this card first (re-read and use theirs).
            winner = CardShortCode.objects.filter(customer_card=customer_card).first()
            if winner is not None:
                return winner.code
    raise RuntimeError("Could not allocate a unique short code")


def resolve(merchant, code: str) -> CustomerCard | None:
    """Resolve a typed short code to a CustomerCard within ``merchant``.

    Case/space-insensitive. Returns ``None`` if unknown or cross-tenant.
    """
    normalized = (code or "").strip().upper().replace(" ", "")
    if not normalized:
        return None
    row = (
        CardShortCode.objects.select_related("customer_card")
        .filter(merchant=merchant, code=normalized)
        .first()
    )
    return row.customer_card if row is not None else None
