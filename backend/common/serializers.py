"""Shared serializer bases (contract §3.7: snake_case JSON keys).

DRF already emits snake_case from snake_case model fields, so these bases simply
give the two phases a single import to extend rather than re-deriving locally.
"""

from __future__ import annotations

from rest_framework import serializers


class BaseSerializer(serializers.Serializer):
    """Base for non-model (request/response) serializers."""


class BaseModelSerializer(serializers.ModelSerializer):
    """Base for model serializers; keeps a consistent place for shared config."""
