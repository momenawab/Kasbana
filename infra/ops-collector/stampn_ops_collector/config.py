from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Collector configuration. Tokens must be supplied by the host .env only."""

    token: str
    environment: str
    location: str
    max_log_lines: int

    @classmethod
    def load(cls) -> "Settings":
        token = os.environ.get("OPS_COLLECTOR_TOKEN", "")
        if len(token) < 32:
            raise RuntimeError("OPS_COLLECTOR_TOKEN must be at least 32 characters")
        return cls(
            token=token,
            environment=os.environ.get("OPS_ENVIRONMENT", "production"),
            location=os.environ.get("OPS_SERVER_LOCATION", "unknown"),
            max_log_lines=min(max(int(os.environ.get("OPS_MAX_LOG_LINES", "80")), 10), 200),
        )


settings = Settings.load()
