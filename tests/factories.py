"""factory_boy factories for the core models (contract §3.4)."""

from __future__ import annotations

import factory
from django.contrib.auth import get_user_model

from core import models
from core.enums import CardStatus, CardType, Role

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    # set_password hashes the raw value (overridable via password=...); the
    # post-generation save deprecation warning is filtered in pyproject.toml.
    password = factory.PostGenerationMethodCall("set_password", "pw12345!")


class MerchantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Merchant

    name = factory.Sequence(lambda n: f"Merchant {n}")
    slug = factory.Sequence(lambda n: f"merchant-{n}")


class LocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Location

    merchant = factory.SubFactory(MerchantFactory)
    name = factory.Sequence(lambda n: f"Branch {n}")


class CardFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Card

    merchant = factory.SubFactory(MerchantFactory)
    type = CardType.STAMP
    name = factory.Sequence(lambda n: f"Card {n}")
    stamps_required = 5
    reward_title = "Free coffee"
    status = CardStatus.ACTIVE


class CustomerCardFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.CustomerCard

    card = factory.SubFactory(CardFactory)
    merchant = factory.SelfAttribute("card.merchant")
    customer_phone = factory.Sequence(lambda n: f"+2010000000{n:02d}")


class RewardFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Reward

    card = factory.SubFactory(CardFactory)
    title = "Free coffee"
    threshold = 5


class StaffUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.StaffUser

    merchant = factory.SubFactory(MerchantFactory)
    user = factory.SubFactory(UserFactory)
    role = Role.ADMIN
