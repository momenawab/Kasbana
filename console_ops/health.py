"""Deterministic global health scoring and alert candidates."""

from __future__ import annotations

from typing import Any


def evaluate(
    payload: dict[str, Any], thresholds: dict[str, float]
) -> tuple[int, str, list[dict[str, str]]]:
    server = payload.get("server", {})
    penalties: list[dict[str, str]] = []
    checks = (
        ("cpu", server.get("cpu_percent"), "cpu_warning", "cpu_critical"),
        ("ram", server.get("ram_percent"), "ram_warning", "ram_critical"),
        ("disk", server.get("disk_percent"), "disk_warning", "disk_critical"),
    )
    score = 100
    for label, value, warning, critical in checks:
        if value is None:
            continue
        if value >= thresholds[critical]:
            score -= 25
            penalties.append({"severity": "critical", "reason": f"{label} is {value}%"})
        elif value >= thresholds[warning]:
            score -= 10
            penalties.append({"severity": "warning", "reason": f"{label} is {value}%"})
    if not payload.get("available", True):
        score = min(score, 20)
        penalties.append({"severity": "critical", "reason": "host collector unavailable"})
    docker = payload.get("docker", {})
    if docker.get("stopped", 0) or docker.get("restarting", 0):
        score -= 20
        penalties.append({"severity": "critical", "reason": "a platform container is not stable"})
    score = max(0, score)
    return score, "healthy" if score >= 90 else "warning" if score >= 60 else "critical", penalties
