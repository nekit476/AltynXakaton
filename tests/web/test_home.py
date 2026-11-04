"""Главная страница каркаса и общий шаблон base.html."""

import allure
from pytest_django.asserts import assertContains, assertTemplateUsed


@allure.feature("Интерфейс")
@allure.story("Каркас страниц")
class TestHome:
    """Главная и общие элементы каждой страницы.

    Тесты:
      1. Главная открывается и собрана на base.html
      2. Страница помечена как концепт и закрыта от индексации
    """

    @allure.title("Главная открывается и собрана на base.html")
    def test_home_renders_on_base_template(self, client):
        response = client.get("/")

        assert response.status_code == 200
        assertTemplateUsed(response, "web/home.html")
        assertTemplateUsed(response, "base.html")

    @allure.title("Плашка «Концепт» и noindex на странице")
    def test_page_marked_as_concept(self, client):
        response = client.get("/")

        assertContains(response, "Концепт для конкурса")
        assertContains(response, '<meta name="robots" content="noindex, nofollow">', html=True)
