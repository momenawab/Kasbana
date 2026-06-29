"""Stampn backend project package.

Ensure the Celery app is imported when Django starts so that the ``shared_task``
decorator and ``@app.task`` registrations work everywhere.
"""

from .celery import app as celery_app

__all__ = ["celery_app"]
