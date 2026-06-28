"""Loyalty serializers (contract §3.6 — snake_case JSON keys).

Request/response shapes for ``/api/v1/loyalty/{stamp,redeem,cards/{id}}``. The
balance math and anti-fraud live in ``core/ledger.py``; these serializers only
validate the wire format and never touch the ledger.
"""

from __future__ import annotations

from rest_framework import serializers


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
    """GET /loyalty/cards/{customer_card_id} response."""

    customer_card_id = serializers.UUIDField()
    customer_name = serializers.CharField(allow_blank=True)
    stamp_count = serializers.IntegerField()
    stamps_required = serializers.IntegerField()
    reward_ready = serializers.BooleanField()
    status = serializers.CharField()
