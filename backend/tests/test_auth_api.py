"""Tests for the auth + infra endpoints (contract §3.6 Auth)."""

from __future__ import annotations

import pytest

from tests import factories

pytestmark = pytest.mark.django_db


def test_health_endpoint(api_client):
    resp = api_client.get("/api/health/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_schema_endpoint_serves_openapi(api_client):
    resp = api_client.get("/api/schema/")
    assert resp.status_code == 200


def test_token_obtain_with_email(api_client):
    factories.UserFactory(email="owner@example.com", password="pw12345!")
    resp = api_client.post(
        "/api/v1/auth/token",
        {"email": "owner@example.com", "password": "pw12345!"},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access" in body and "refresh" in body


def test_token_refresh(api_client):
    factories.UserFactory(email="owner2@example.com", password="pw12345!")
    pair = api_client.post(
        "/api/v1/auth/token",
        {"email": "owner2@example.com", "password": "pw12345!"},
        format="json",
    ).json()
    resp = api_client.post("/api/v1/auth/refresh", {"refresh": pair["refresh"]}, format="json")
    assert resp.status_code == 200
    assert "access" in resp.json()


def test_bad_credentials_return_401_envelope(api_client):
    factories.UserFactory(email="owner3@example.com", password="pw12345!")
    resp = api_client.post(
        "/api/v1/auth/token",
        {"email": "owner3@example.com", "password": "wrong"},
        format="json",
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_missing_fields_return_validation_envelope(api_client):
    resp = api_client.post("/api/v1/auth/token", {"email": "x@example.com"}, format="json")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "password" in body["error"]["fields"]
