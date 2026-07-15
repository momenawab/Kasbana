# Generated for the wallet-templates feature (layout-locked pass templates).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wallets", "0006_walletcarddesign_google_stamp_hero"),
    ]

    operations = [
        migrations.AddField(
            model_name="walletcarddesign",
            name="template_key",
            field=models.CharField(default="custom", max_length=40),
        ),
        migrations.AddField(
            model_name="walletcarddesign",
            name="bottom_image_url",
            field=models.URLField(blank=True),
        ),
    ]
