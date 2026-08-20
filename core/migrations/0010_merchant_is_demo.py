from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_alter_merchant_plan_enterprise"),
    ]

    operations = [
        migrations.AddField(
            model_name="merchant",
            name="is_demo",
            field=models.BooleanField(default=False),
        ),
    ]
