"""Console Celery tasks (Phase 10)."""

from __future__ import annotations

from celery import shared_task
from django.utils import timezone

from console import announcements
from console.models import Announcement


@shared_task(queue="default")
def send_due_announcements() -> int:
    """Send any SCHEDULED announcement whose time has arrived. Beat: every 5 min.

    ``announcements.send`` flips the row to SENT, so a re-run never double-sends.
    """
    due = Announcement.objects.filter(
        status=Announcement.Status.SCHEDULED, schedule_at__lte=timezone.now()
    )
    sent = 0
    for announcement in due:
        announcements.send(announcement)
        sent += 1
    return sent
