"""Своя модель пользователя: роль по умолчанию, суперпользователь, UUID, ФИО."""

import uuid

import allure
import pytest
from django.contrib.auth import get_user_model

from core.users.models import Role, User

# Пароль только для тестов; хешер в тестах быстрый (core/settings/test.py).
PASSWORD = "test-password-123"

FULL_NAME_CASES = [
    pytest.param("Иванов", "Иван", "Иванович", "Иванов Иван Иванович", id="full"),
    pytest.param("Смит", "Джон", "", "Смит Джон", id="no-patronymic"),
    pytest.param("", "", "", "", id="empty"),
]


@allure.feature("Платформа")
@allure.story("Модель пользователя")
class TestUserModel:
    """Модель пользователя, заданная в первой миграции.

    Тесты:
      1. Проект использует свою модель пользователя
      2. Пользователь без явной роли получает наименьшие права — «студент»
      3. Суперпользователь получает роль «администратор»
      4. Явно переданная роль суперпользователя не перетирается
      5. Первичный ключ — случайный UUID, а не счётчик
      6. ФИО собирается в русском порядке, пустые части пропускаются
      7. Пользователь без ФИО показывается логином
    """

    @allure.title("AUTH_USER_MODEL указывает на core.users.User")
    def test_custom_user_model_is_used(self):
        assert get_user_model() is User

    @pytest.mark.django_db
    @allure.title("Пользователь без явной роли — студент")
    def test_default_role_is_student(self):
        user = User.objects.create_user(username="ivanov", password=PASSWORD)

        assert user.role == Role.STUDENT
        assert not user.is_staff

    @pytest.mark.django_db
    @allure.title("Суперпользователь получает роль «администратор»")
    def test_superuser_gets_admin_role(self):
        user = User.objects.create_superuser("root", "root@example.com", PASSWORD)

        assert user.role == Role.ADMIN
        assert user.is_superuser

    @pytest.mark.django_db
    @allure.title("Явная роль суперпользователя сохраняется")
    def test_superuser_explicit_role_is_kept(self):
        user = User.objects.create_superuser(
            "teacher-root", "t@example.com", PASSWORD, role=Role.TEACHER
        )

        assert user.role == Role.TEACHER

    @pytest.mark.django_db
    @allure.title("Первичный ключ пользователя — UUID")
    def test_primary_key_is_random_uuid(self):
        first = User.objects.create_user(username="first", password=PASSWORD)
        second = User.objects.create_user(username="second", password=PASSWORD)

        assert isinstance(first.pk, uuid.UUID)
        # uuid4 — случайный: соседние пользователи не получают соседние id.
        assert first.pk.version == 4
        assert first.pk != second.pk

    @pytest.mark.parametrize(("last", "first", "patronymic", "expected"), FULL_NAME_CASES)
    @allure.title("ФИО «{expected}» из частей «{last}», «{first}», «{patronymic}»")
    def test_full_name_order(self, last, first, patronymic, expected):
        user = User(last_name=last, first_name=first, patronymic=patronymic)

        assert user.get_full_name() == expected

    @allure.title("Пользователь без ФИО показывается логином")
    def test_str_falls_back_to_username(self):
        user = User(username="petrov")

        assert str(user) == "petrov"
