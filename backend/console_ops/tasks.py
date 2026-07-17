from __future__ import annotations

from celery import shared_task

from .models import OpsConfiguration
from .services import dashboard, in_quiet_hours, take_snapshot
from .telegram import send


@shared_task(queue="default")
def collect_snapshot() -> dict:
    return take_snapshot()


@shared_task(queue="default")
def send_hourly_report() -> bool:
    config = OpsConfiguration.current()
    if not (config.hourly_reports_enabled and not in_quiet_hours(config)):
        return False
    d = dashboard()
    s = d.get("server", {})
    return send(
        config,
        "\n".join(
            [
                f"{'🟢' if d['status'] == 'healthy' else '🟠'} Stampn Production",
                f"Health Score: {d['health_score']}%",
                f"CPU: {s.get('cpu_percent', '—')}%",
                f"RAM: {s.get('ram_percent', '—')}%",
                f"Disk: {s.get('disk_percent', '—')}%",
                f"Docker: {d.get('docker', {}).get('running', '—')} running",
                f"API: {'Healthy' if d.get('api', {}).get('ok') else 'Unavailable'}",
                f"Version: {d.get('version', '—')}",
            ]
        ),
    )
