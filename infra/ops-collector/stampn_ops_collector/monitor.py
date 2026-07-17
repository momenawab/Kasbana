from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import docker
import psutil

from .config import settings
from .redact import redact


def _percent(part: float, total: float) -> float:
    return round((part / total * 100) if total else 0, 2)


def _container(client: docker.DockerClient, item: Any) -> dict[str, Any]:
    attrs = item.attrs
    state = attrs.get("State", {})
    stats: dict[str, Any] = {}
    try:
        stats = item.stats(stream=False)
    except docker.errors.APIError:
        # A container may disappear between list and stats.  It is still useful
        # to surface its state rather than fail the whole snapshot.
        pass
    cpu_total = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
    cpu_prev = stats.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
    system_total = stats.get("cpu_stats", {}).get("system_cpu_usage", 0)
    system_prev = stats.get("precpu_stats", {}).get("system_cpu_usage", 0)
    cpus = len(stats.get("cpu_stats", {}).get("cpu_usage", {}).get("percpu_usage", []) or [1])
    cpu = _percent((cpu_total - cpu_prev) * cpus, system_total - system_prev)
    memory = stats.get("memory_stats", {})
    used = max(memory.get("usage", 0) - memory.get("stats", {}).get("cache", 0), 0)
    limit = memory.get("limit", 0)
    health = state.get("Health", {}).get("Status", "unknown")
    return {
        "id": item.id[:12],
        "name": item.name,
        "image": (attrs.get("Config", {}).get("Image") or "").split("@", 1)[0],
        "status": state.get("Status", "unknown"),
        "health": health,
        "started_at": state.get("StartedAt"),
        "restart_count": attrs.get("RestartCount", 0),
        "cpu_percent": cpu,
        "memory_bytes": used,
        "memory_limit_bytes": limit,
        "memory_percent": _percent(used, limit),
    }


def _logs(client: docker.DockerClient) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in client.containers.list(all=True):
        try:
            text = item.logs(tail=settings.max_log_lines, timestamps=True).decode("utf-8", "replace")
        except docker.errors.APIError:
            continue
        for line in text.splitlines()[-settings.max_log_lines :]:
            result.append({"container": item.name, "line": redact(line)[:2000]})
    return result[-settings.max_log_lines :]


def snapshot(include_logs: bool = False) -> dict[str, Any]:
    """Return bounded, JSON-safe host facts. No command execution is ever used."""

    boot = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/host")
    net = psutil.net_io_counters()
    load = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0.0, 0.0, 0.0)
    client = docker.DockerClient(base_url="unix:///var/run/docker.sock", version="auto", timeout=3)
    containers = [_container(client, item) for item in client.containers.list(all=True)]
    running = sum(item["status"] == "running" for item in containers)
    restarting = sum(item["status"] == "restarting" for item in containers)
    payload: dict[str, Any] = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "environment": settings.environment,
        "location": settings.location,
        "server": {
            "cpu_percent": psutil.cpu_percent(interval=0.15),
            "ram_percent": memory.percent,
            "ram_used_bytes": memory.used,
            "ram_total_bytes": memory.total,
            "disk_percent": disk.percent,
            "disk_free_bytes": disk.free,
            "disk_total_bytes": disk.total,
            "swap_percent": swap.percent,
            "load_1": round(load[0], 2),
            "load_5": round(load[1], 2),
            "load_15": round(load[2], 2),
            "network_bytes_sent": net.bytes_sent,
            "network_bytes_received": net.bytes_recv,
            "booted_at": boot.isoformat(),
            "uptime_seconds": int(time.time() - boot.timestamp()),
        },
        "docker": {
            "running": running,
            "stopped": len(containers) - running - restarting,
            "restarting": restarting,
            "containers": containers,
        },
    }
    if include_logs:
        payload["logs"] = _logs(client)
    return payload
