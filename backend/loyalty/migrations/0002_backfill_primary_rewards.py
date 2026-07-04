"""Backfill a Reward row for every card that has a reward but no row (note 7).

The single-reward card flow only stored the reward on ``Card`` (``reward_title``/
``reward_description``); nothing ever created the ``Reward`` *row* the redeem flow
needs. Existing prod cards therefore have full customers who can't be given their
reward ("Give reward" stays disabled). Create the missing primary rows so those
customers can redeem. New/edited cards are kept in sync by
``dashboard.views._sync_primary_reward``.
"""

from __future__ import annotations

from django.db import migrations


def backfill_rewards(apps, schema_editor):
    Card = apps.get_model("core", "Card")
    Reward = apps.get_model("core", "Reward")
    for card in Card.objects.exclude(reward_title="").filter(rewards__isnull=True):
        Reward.objects.create(
            card=card,
            title=card.reward_title,
            description=card.reward_description,
            threshold=card.stamps_required,
            is_active=True,
        )


def noop_reverse(apps, schema_editor):
    # Backfilled rows are indistinguishable from user-created ones; leave them.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("loyalty", "0001_initial"),
        ("core", "0007_card_referral_enabled"),
    ]

    operations = [
        migrations.RunPython(backfill_rewards, noop_reverse),
    ]
