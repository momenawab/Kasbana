"""Persistent, platform-owned Ops data. No merchant data belongs here."""

from __future__ import annotations

from django.db import models

from core.models import TimeStampedModel, UUIDModel


class OpsConfiguration(TimeStampedModel):
    """Singleton encrypted notification settings and configurable thresholds."""

    singleton = models.BooleanField(default=True, unique=True, editable=False)
    telegram_bot_token_encrypted = models.BinaryField(blank=True, editable=False)
    telegram_chat_id = models.CharField(max_length=80, blank=True)
    notifications_enabled = models.BooleanField(default=False)
    hourly_reports_enabled = models.BooleanField(default=True)
    critical_alerts_enabled = models.BooleanField(default=True)
    warning_alerts_enabled = models.BooleanField(default=True)
    deployment_alerts_enabled = models.BooleanField(default=True)
    backup_alerts_enabled = models.BooleanField(default=True)
    ssl_alerts_enabled = models.BooleanField(default=True)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    thresholds = models.JSONField(default=dict, blank=True)

    @classmethod
    def defaults(cls) -> dict[str, float]:
        return {
            "cpu_warning": 80,
            "cpu_critical": 90,
            "ram_warning": 80,
            "ram_critical": 90,
            "disk_warning": 80,
            "disk_critical": 90,
            "load_warning": 2.0,
            "response_time_warning_ms": 500,
            "error_rate_warning": 5,
            "queue_size_warning": 100,
            "failed_jobs_warning": 10,
        }

    @classmethod
    def current(cls) -> OpsConfiguration:
        obj, _ = cls.objects.get_or_create(singleton=True, defaults={"thresholds": cls.defaults()})
        if not obj.thresholds:
            obj.thresholds = cls.defaults()
            obj.save(update_fields=["thresholds", "updated_at"])
        return obj


class OpsSnapshot(UUIDModel):
    observed_at = models.DateTimeField(db_index=True)
    health_score = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16)
    payload = models.JSONField()

    class Meta:
        ordering = ["-observed_at"]


class OpsAlert(UUIDModel, TimeStampedModel):
    fingerprint = models.CharField(max_length=160, unique=True)
    severity = models.CharField(max_length=12)
    status = models.CharField(max_length=12, default="open")
    title = models.CharField(max_length=200)
    detail = models.TextField(blank=True)
    first_seen_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    occurrences = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-last_seen_at"]


class OpsDeployment(UUIDModel, TimeStampedModel):
    commit_sha = models.CharField(max_length=64, db_index=True)
    branch = models.CharField(max_length=80)
    message = models.CharField(max_length=500, blank=True)
    deployed_by = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=16)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
