"""Celery application for the Stampn backend.

Queues (contract §3.9): ``default``, ``wallet``, ``messaging``.
Task names are canonical and defined in each app's ``tasks.py``; never duplicate.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("stampn")

# Read config from Django settings, the CELERY_ namespace.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Discover tasks.py in every installed app.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:  # pragma: no cover - diagnostic helper
    print(f"Request: {self.request!r}")
