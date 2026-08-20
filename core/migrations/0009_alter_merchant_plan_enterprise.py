# PlanTier gained ENTERPRISE (additive; see core/enums.py). This is a `choices`
# change only — Django keeps choices out of the database, so the operation
# rewrites no rows and no existing merchant's plan changes. It exists so
# makemigrations --check stays clean and the field's state matches the enum.
#
# `core` is frozen (contract §3.2): this migration accompanies an agreed
# additive enum value, not a redefinition. Nothing here alters FREE/STARTER/
# GROWTH/CHAIN.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_remove_customercard_uniq_card_customer_phone_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='merchant',
            name='plan',
            field=models.CharField(choices=[('FREE', 'Free'), ('STARTER', 'Starter'), ('GROWTH', 'Growth'), ('CHAIN', 'Chain'), ('ENTERPRISE', 'Enterprise')], default='FREE', max_length=16),
        ),
    ]
