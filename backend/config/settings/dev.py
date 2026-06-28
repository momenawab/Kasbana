"""Local development settings."""

from __future__ import annotations

from .base import *  # noqa: F401,F403
from .base import env_list

DEBUG = True

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0")

# Celery runs tasks inline during local dev so no broker is required for the
# Phase 1.0 exit-criteria shell.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
