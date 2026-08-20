from __future__ import annotations

import re

_SECRET = re.compile(
    r"(?i)(authorization|password|secret|token|api[_-]?key)(\s*[=:]\s*)([^\s,;]+)"
)


def redact(value: str) -> str:
    """Keep diagnostic context while preventing common secret-shaped values leaking."""

    return _SECRET.sub(r"\1\2[REDACTED]", value)
