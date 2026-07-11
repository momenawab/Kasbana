"""Structured logging: a request-ID context + a dependency-free JSON formatter.

The request ID is stamped by ``common.middleware.RequestIDMiddleware`` into a
``ContextVar`` so any log record emitted while handling that request carries it —
no need to thread the id through call sites. ``RequestIDFilter`` reads the var
onto every record; ``JSONFormatter`` renders one JSON object per line so logs are
queryable in prod. Celery tasks (no request) log ``request_id="-"``.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from contextvars import ContextVar

# Set per-request in middleware; "-" outside a request (Celery, management cmds).
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDFilter(logging.Filter):
    """Attach the current request id to every record as ``record.request_id``."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


# LogRecord attributes that are intrinsic — everything else a caller passed via
# ``extra=`` is merged into the JSON so structured fields survive.
_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "request_id",
    "message",
    "asctime",
    "taskName",
}


class JSONFormatter(logging.Formatter):
    """Render a log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": _dt.datetime.fromtimestamp(record.created, tz=_dt.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Merge any structured ``extra=`` fields the caller attached.
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str, ensure_ascii=False)
