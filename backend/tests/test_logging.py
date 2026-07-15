"""Structured logging tests (Phase D).

Covers the JSON formatter (structured fields + request id + exception), the
request-id filter/context, and the RequestIDMiddleware end-to-end: a minted id
echoed on the response, an inbound id reused, and the id visible to a log record
emitted while the request is in flight.
"""

from __future__ import annotations

import json
import logging

import pytest

from common.logging import JSONFormatter, RequestIDFilter, request_id_var
from common.middleware import REQUEST_ID_HEADER, RequestIDMiddleware


def _record(msg="hi", **extra):
    rec = logging.LogRecord("test.logger", logging.INFO, __file__, 1, msg, (), None)
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


def _render(rec):
    RequestIDFilter().filter(rec)
    return json.loads(JSONFormatter().format(rec))


def test_json_formatter_emits_core_fields():
    token = request_id_var.set("req-abc")
    try:
        payload = _render(_record("hello"))
    finally:
        request_id_var.reset(token)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["msg"] == "hello"
    assert payload["request_id"] == "req-abc"
    assert "ts" in payload


def test_json_formatter_merges_extra_fields():
    payload = _render(_record("scan", merchant_id="m1", card_id="c9"))
    assert payload["merchant_id"] == "m1"
    assert payload["card_id"] == "c9"


def test_json_formatter_includes_exception():
    import sys

    try:
        raise ValueError("boom")
    except ValueError:
        rec = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())
    payload = _render(rec)
    assert "ValueError: boom" in payload["exc"]


def test_filter_defaults_to_dash_outside_a_request():
    rec = _record()
    RequestIDFilter().filter(rec)
    assert rec.request_id == "-"


# -- middleware --------------------------------------------------------------


def _ok_view(request):
    from django.http import HttpResponse

    return HttpResponse("ok")


def test_middleware_mints_and_echoes_a_request_id():
    from django.test import RequestFactory

    seen = {}

    def view(request):
        from django.http import HttpResponse

        seen["id"] = request_id_var.get()
        seen["attr"] = request.request_id
        return HttpResponse("ok")

    resp = RequestIDMiddleware(view)(RequestFactory().get("/"))
    assert resp[REQUEST_ID_HEADER]
    assert seen["id"] == resp[REQUEST_ID_HEADER]
    assert seen["attr"] == resp[REQUEST_ID_HEADER]


def test_middleware_reuses_an_inbound_id():
    from django.test import RequestFactory

    resp = RequestIDMiddleware(_ok_view)(RequestFactory().get("/", HTTP_X_REQUEST_ID="edge-42"))
    assert resp[REQUEST_ID_HEADER] == "edge-42"


def test_middleware_caps_an_oversized_inbound_id():
    from django.test import RequestFactory

    resp = RequestIDMiddleware(_ok_view)(RequestFactory().get("/", HTTP_X_REQUEST_ID="z" * 500))
    assert len(resp[REQUEST_ID_HEADER]) == 64


def test_context_var_resets_after_the_request():
    from django.test import RequestFactory

    RequestIDMiddleware(_ok_view)(RequestFactory().get("/"))
    assert request_id_var.get() == "-"


@pytest.mark.django_db
def test_response_header_present_through_the_real_stack(client):
    resp = client.get("/api/health/")
    assert resp.headers.get(REQUEST_ID_HEADER)
