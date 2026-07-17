from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from .config import settings
from .monitor import snapshot

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def _authorize(token: Annotated[str | None, Header(alias="X-Ops-Collector-Token")] = None) -> None:
    if token is None or not secrets.compare_digest(token, settings.token):
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/snapshot")
def get_snapshot(
    include_logs: Annotated[bool, Query()] = False,
    _authorized: Annotated[None, Depends(_authorize)] = None,
) -> dict:
    return snapshot(include_logs=include_logs)
