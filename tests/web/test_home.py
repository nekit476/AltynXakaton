"""Главная страница каркаса и общий шаблон base.html."""

import allure
import pytest
from pytest_django.asserts import assertContains, assertTemplateUsed

ROLE_CLIENTS = [
    pytest.param("student_client", id="student"),
    pytest.param("teacher_client", id="teacher"),
    pytest.param("administrator_client", id="administrator"),
]


@allure.feature("Интерфейс")
@allure.story("Каркас страниц")
class TestHome:
    """Главная и общие элементы каждой страницы.

    Тесты:
      1. Главная открывается каждой роли и собрана на base.html
      2. Страница помечена как концепт и закрыта от индексации
      3. Вошедший видит своё имя и кнопку выхода
    """

    @pytest.mark.parametrize("client_fixture", ROLE_CLIENTS)
    @allure.title("Главная открывается роли {client_fixture}")
    def test_home_renders_for_each_role(self, request, client_fixture):
        client = request.getfixturevalue(client_fixture)

        response = client.get("/")

        assert response.status_code == 200
        assertTemplateUsed(response, "web/home.html")
        assertTemplateUsed(response, "base.html")

    # Страница входа — публичная, на ней проверяем общий каркас без входа.
    @pytest.mark.django_db
    @allure.title("Плашка «Концепт» и noindex на странице")
    def test_page_marked_as_concept(self, client):
        response = client.get("/login/")

        assertContains(response, "Концепт для конкурса")
        assertContains(response, '<meta name="robots" content="noindex, nofollow">', html=True)

    @allure.title("Вошедший видит своё имя и кнопку выхода")
    def test_userbar(self, student_client, student):
        response = student_client.get("/")

        assertContains(response, student.get_full_name())
        assertContains(response, 'action="/logout/"')
