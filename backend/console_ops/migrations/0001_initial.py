from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name="OpsConfiguration", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
            ("telegram_bot_token_encrypted", models.BinaryField(blank=True, editable=False)),
            ("telegram_chat_id", models.CharField(blank=True, max_length=80)),
            ("notifications_enabled", models.BooleanField(default=False)), ("hourly_reports_enabled", models.BooleanField(default=True)),
            ("critical_alerts_enabled", models.BooleanField(default=True)), ("warning_alerts_enabled", models.BooleanField(default=True)),
            ("deployment_alerts_enabled", models.BooleanField(default=True)), ("backup_alerts_enabled", models.BooleanField(default=True)), ("ssl_alerts_enabled", models.BooleanField(default=True)),
            ("quiet_hours_start", models.TimeField(blank=True, null=True)), ("quiet_hours_end", models.TimeField(blank=True, null=True)), ("thresholds", models.JSONField(blank=True, default=dict)),
        ]),
        migrations.CreateModel(name="OpsSnapshot", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("observed_at", models.DateTimeField(db_index=True)), ("health_score", models.PositiveSmallIntegerField()), ("status", models.CharField(max_length=16)), ("payload", models.JSONField()),
        ], options={"ordering": ["-observed_at"]}),
        migrations.CreateModel(name="OpsAlert", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("fingerprint", models.CharField(max_length=160, unique=True)), ("severity", models.CharField(max_length=12)), ("status", models.CharField(default="open", max_length=12)), ("title", models.CharField(max_length=200)), ("detail", models.TextField(blank=True)), ("first_seen_at", models.DateTimeField()), ("last_seen_at", models.DateTimeField()), ("resolved_at", models.DateTimeField(blank=True, null=True)), ("occurrences", models.PositiveIntegerField(default=1)),
        ], options={"ordering": ["-last_seen_at"]}),
        migrations.CreateModel(name="OpsDeployment", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("commit_sha", models.CharField(db_index=True, max_length=64)), ("branch", models.CharField(max_length=80)), ("message", models.CharField(blank=True, max_length=500)), ("deployed_by", models.CharField(blank=True, max_length=180)), ("status", models.CharField(max_length=16)), ("started_at", models.DateTimeField()), ("finished_at", models.DateTimeField(blank=True, null=True)), ("duration_seconds", models.PositiveIntegerField(blank=True, null=True)),
        ]),
    ]
