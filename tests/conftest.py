"""Общие фикстуры для всех тестов: пользователи ролей и клиенты, уже вошедшие под ними.

Вход в клиентах — через force_login: обычный client.login() не проходит django-axes,
которому для проверки перебора нужен запрос. Сам вход формой проверяется в tests/core.

Фикстуры одного модуля живут в его tests/<модуль>/conftest.py.
"""

import factory.random
import pytest

from core.users.models import Role
from tests.factories import UserFactory

# Фиксированное зерно: данные Faker одинаковы от прогона к прогону, падение воспроизводится.
FACTORY_SEED = "zachetka"


@pytest.fixture(autouse=True, scope="session")
def _reseed_factories():
    factory.random.reseed_random(FACTORY_SEED)


@pytest.fixture
def make_user(db):
    """Фабрика пользователей: make_user(role=Role.TEACHER, username="ivanov")."""
    return UserFactory


@pytest.fixture
def student(make_user):
    return make_user(role=Role.STUDENT)


@pytest.fixture
def other_student(make_user):
    """Второй студент — для проверок «студент 1 не видит данных студента 2»."""
    return make_user(role=Role.STUDENT)


@pytest.fixture
def teacher(make_user):
    return make_user(role=Role.TEACHER)


@pytest.fixture
def administrator(make_user):
    """Роль «администратор». Не путать с admin_user из pytest-django — тот суперпользователь."""
    return make_user(role=Role.ADMIN)


@pytest.fixture
def login_client(client):
    """Фабрика: login_client(user) — клиент, вошедший под пользователем."""

    def factory_(user):
        client.force_login(user)
        return client

    return factory_


@pytest.fixture
def student_client(login_client, student):
    return login_client(student)


@pytest.fixture
def teacher_client(login_client, teacher):
    return login_client(teacher)


@pytest.fixture
def administrator_client(login_client, administrator):
    return login_client(administrator)


@pytest.fixture
def htmx_headers():
    """Заголовки HTMX-запроса: client.get(url, headers=htmx_headers)."""
    return {"HX-Request": "true"}
