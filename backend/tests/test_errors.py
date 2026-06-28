"""Tests for the error envelope + code mapping (contract §3.7)."""

from __future__ import annotations

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from common.errors import ErrorCode, RewardNotReady, exception_handler


def _handle(exc):
    return exception_handler(exc, {})


def test_not_found_maps_to_code():
    resp = _handle(NotFound())
    assert resp.status_code == 404
    assert resp.data["error"]["code"] == ErrorCode.NOT_FOUND
    assert "message" in resp.data["error"]


def test_permission_denied_maps_to_code():
    resp = _handle(PermissionDenied())
    assert resp.data["error"]["code"] == ErrorCode.PERMISSION_DENIED


def test_validation_error_carries_fields():
    resp = _handle(ValidationError({"customer_phone": ["This field is required."]}))
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == ErrorCode.VALIDATION_ERROR
    assert resp.data["error"]["fields"]["customer_phone"] == ["This field is required."]


def test_domain_exception_maps_to_code_and_status():
    resp = _handle(RewardNotReady())
    assert resp.status_code == 422
    assert resp.data["error"]["code"] == ErrorCode.REWARD_NOT_READY
