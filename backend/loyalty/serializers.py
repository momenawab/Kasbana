"""Loyalty serializers (contract §3.6 — snake_case JSON keys).

Request/response shapes for ``/api/v1/loyalty/{stamp,redeem,cards/{id}}``. The
balance math and anti-fraud live in ``core/ledger.py``; these serializers only
validate the wire format and never touch the ledger.
"""

from __future__ import annotations

import uuid

from rest_framework import serializers

from core import constants


class ScanRequestSerializer(serializers.Serializer):
    """POST /loyalty/scan request body.

    ``code`` is the raw payload read from the customer's wallet QR/barcode:
    ``{PASS_BARCODE_PREFIX}{customer_card.id.hex}`` (see ``wallets`` builders).
    We validate the prefix + hex here and expose the parsed ``customer_card_id``
    so the view only does tenant scoping — the wire format stays server-owned
    (the cashier UI never has to know the prefix).
    """

    code = serializers.CharField(max_length=64, trim_whitespace=True)

    def validate_code(self, value: str) -> uuid.UUID:
        prefix = constants.PASS_BARCODE_PREFIX
        if not value.startswith(prefix):
            raise serializers.ValidationError("Unrecognized wallet code.")
        try:
            return uuid.UUID(hex=value[len(prefix) :])
        except ValueError as exc:
            raise serializers.ValidationError("Unrecognized wallet code.") from exc


class StampRequestSerializer(serializers.Serializer):
    """POST /loyalty/stamp request body."""

    customer_card_id = serializers.UUIDField()
    # Contract default is 1; reject zero/negative so a stamp only ever adds.
    delta = serializers.IntegerField(required=False, default=1, min_value=1)


class StampResponseSerializer(serializers.Serializer):
    """POST /loyalty/stamp success response."""

    customer_card_id = serializers.UUIDField()
    stamp_count = serializers.IntegerField()
    stamps_required = serializers.IntegerField()
    reward_ready = serializers.BooleanField()


class RedeemRequestSerializer(serializers.Serializer):
    """POST /loyalty/redeem request body."""

    customer_card_id = serializers.UUIDField()
    reward_id = serializers.UUIDField()


class RedeemResponseSerializer(serializers.Serializer):
    """POST /loyalty/redeem success response."""

    redemption_id = serializers.UUIDField()
    status = serializers.CharField()
    stamp_count = serializers.IntegerField()


class CardStateSerializer(serializers.Serializer):
    """GET /loyalty/cards/{customer_card_id} + POST /loyalty/scan response.

    ``reward_id``/``reward_title`` describe the program's active reward so the
    cashier (scan) UI can redeem in one tap; both are null/blank when the program
    has no active reward configured.
    """

    customer_card_id = serializers.UUIDField()
    customer_name = serializers.CharField(allow_blank=True)
    stamp_count = serializers.IntegerField()
    stamps_required = serializers.IntegerField()
    reward_ready = serializers.BooleanField()
    status = serializers.CharField()
    reward_id = serializers.UUIDField(allow_null=True, required=False)
    reward_title = serializers.CharField(allow_blank=True, required=False)
