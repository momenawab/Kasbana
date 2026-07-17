from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="WhatsAppIdentity", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("phone", models.CharField(db_index=True, max_length=16, unique=True)), ("verified_at", models.DateTimeField(auto_now_add=True)), ("user", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="whatsapp_identity", to=settings.AUTH_USER_MODEL))]),
        migrations.CreateModel(name="WhatsAppMessageLog", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("message_id", models.CharField(blank=True, max_length=128, unique=True)), ("phone_masked", models.CharField(max_length=24)), ("direction", models.CharField(default="outbound", max_length=12)), ("status", models.CharField(default="sent", max_length=32)), ("error", models.TextField(blank=True)), ("meta_response", models.JSONField(blank=True, default=dict)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True))]),
    ]
