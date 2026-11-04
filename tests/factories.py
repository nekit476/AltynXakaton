"""Фабрики factory_boy для общих объектов. Фабрики модулей domain — в tests/domain/<app>/.

Случайные данные воспроизводимы: зерно задаётся в tests/conftest.py.
"""

import factory

from core.users.models import Role, User

# Пароль тестовых пользователей. В тестах хешер быстрый (core/settings/test.py).
TEST_PASSWORD = "test-password-123"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    last_name = factory.Faker("last_name", locale="ru_RU")
    first_name = factory.Faker("first_name", locale="ru_RU")
    patronymic = factory.Faker("middle_name", locale="ru_RU")
    role = Role.STUDENT
    password = factory.django.Password(TEST_PASSWORD)
