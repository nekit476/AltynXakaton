"""Вход и сессии: форма входа, срок сессии, argon2, axes, вход по умолчанию обязателен."""

from datetime import timedelta

import allure
import pytest
from django.contrib.auth.hashers import check_password, make_password
from django.test import override_settings

from core.accounts.sessions import SESSION_AGE_BY_ROLE
from core.settings import base
from core.users.models import Role
from tests.factories import TEST_PASSWORD

LOGIN_URL = "/login/"
# Формат хеша argon2id с параметрами минимума OWASP (03_security.md §10, скриншот для PDF).
ARGON2_PREFIX = "argon2$argon2id$v=19$m=19456,t=2,p=1$"

SESSION_CASES = [
    pytest.param(role, age, id=role.value) for role, age in SESSION_AGE_BY_ROLE.items()
]


def login(client, username, password):
    return client.post(LOGIN_URL, {"username": username, "password": password})


@pytest.mark.django_db
@allure.feature("Вход")
@allure.story("Форма входа")
class TestLogin:
    """Вход по логину и паролю.

    Тесты:
      1. Страница входа открыта без входа
      2. Верный пароль: вход и переход на главную
      3. Неверный пароль и несуществующий логин дают одинаковое сообщение
      4. Срок сессии зависит от роли
      5. После 5 неудач логин блокируется даже для верного пароля, другие логины входят
      6. Выход — только POST
    """

    @allure.title("Страница входа открыта без входа")
    def test_login_page_is_public(self, client):
        response = client.get(LOGIN_URL)

        assert response.status_code == 200
        assert "accounts/login.html" in [t.name for t in response.templates]

    @allure.title("Верный пароль — вход и переход на главную")
    def test_successful_login(self, client, student):
        response = login(client, student.username, TEST_PASSWORD)

        assert response.status_code == 302
        assert response.url == "/"
        assert client.session["_auth_user_id"] == str(student.pk)

    @allure.title("Одинаковое сообщение для чужого логина и неверного пароля")
    def test_same_error_for_unknown_user_and_wrong_password(self, client, student):
        wrong_password = login(client, student.username, "not-the-password")
        unknown_user = login(client, "no-such-user", "not-the-password")

        # Разные сообщения позволили бы перебором узнать, какие логины существуют.
        errors = [r.context["form"].non_field_errors() for r in (wrong_password, unknown_user)]
        assert errors[0] == errors[1]
        assert errors[0]

    @pytest.mark.parametrize(("role", "age"), SESSION_CASES)
    @allure.title("Срок сессии роли {role} — {age}")
    def test_session_age_by_role(self, client, make_user, role, age):
        user = make_user(role=role)

        login(client, user.username, TEST_PASSWORD)

        assert client.session.get_expiry_age() == int(age.total_seconds())

    @allure.title("Перебор пароля блокирует логин, а не всех")
    def test_bruteforce_locks_username(self, client, student, other_student):
        for _ in range(base.AXES_FAILURE_LIMIT):
            login(client, student.username, "wrong-password")

        locked = login(client, student.username, TEST_PASSWORD)
        neighbour = login(client, other_student.username, TEST_PASSWORD)

        assert locked.status_code == 429
        assert neighbour.status_code == 302, "блокировка по логину, а не по IP — сосед входит"

    @allure.title("Выход только POST-запросом")
    def test_logout_requires_post(self, student_client):
        assert student_client.get("/logout/").status_code == 405

        response = student_client.post("/logout/")

        assert response.status_code == 302
        assert "_auth_user_id" not in student_client.session


@allure.feature("Вход")
@allure.story("Хранение паролей")
class TestPasswordHasher:
    """Пароли хранятся только хешами argon2id.

    Тесты:
      1. Хеш — argon2id с m = 19 МиБ, t = 2, p = 1, и пароль по нему проверяется
    """

    # В тестах быстрый хешер; здесь — настоящий список из base.py.
    @override_settings(PASSWORD_HASHERS=base.PASSWORD_HASHERS)
    @allure.title("Хеш argon2id с параметрами OWASP")
    def test_argon2id_parameters(self):
        encoded = make_password(TEST_PASSWORD)

        assert encoded.startswith(ARGON2_PREFIX)
        assert check_password(TEST_PASSWORD, encoded)
        assert not check_password("other-password", encoded)


@allure.feature("Вход")
@allure.story("Вход обязателен")
class TestLoginRequired:
    """Любая страница по умолчанию требует входа (LoginRequiredMiddleware).

    Тесты:
      1. Анонимного с главной отправляют на вход с адресом возврата
      2. HTMX-запрос анонимного получает HX-Redirect вместо 302
    """

    @allure.title("Аноним с главной уходит на вход")
    def test_anonymous_redirected(self, client):
        response = client.get("/")

        assert response.status_code == 302
        assert response.url == "/login/?next=/"

    @allure.title("HTMX-запрос анонимного — HX-Redirect")
    def test_htmx_anonymous_gets_hx_redirect(self, client, htmx_headers):
        response = client.get("/", headers=htmx_headers)

        assert response.status_code == 204
        assert response["HX-Redirect"] == "/login/?next=/"


def test_session_ages_are_ordered():
    """Чем больше прав у роли, тем короче сессия: риск угона растёт с правами."""
    ages = SESSION_AGE_BY_ROLE

    assert ages[Role.STUDENT] > ages[Role.TEACHER] > ages[Role.ADMIN]
    assert ages[Role.ADMIN] <= timedelta(hours=8)
