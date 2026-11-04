"""Служебные адреса /health/ и /ready/."""

import logging

import allure
import pytest
from django.urls import resolve

from core.health import views

# Строка, которой не должно быть в публичном ответе: так выглядел бы хост БД в тексте ошибки.
LEAKED_DETAIL = "secret-db-host:5432"

COMPONENTS = [
    pytest.param("database", id="database"),
    pytest.param("cache", id="cache"),
]

SERVICE_URLS = [
    pytest.param("/health/", id="health"),
    pytest.param("/ready/", id="ready"),
]


@pytest.fixture
def break_component(monkeypatch):
    """Подменяет проверку компонента на падающую с «секретным» текстом ошибки."""

    def factory(name: str) -> None:
        def failing_check() -> None:
            raise RuntimeError(f"connection to {LEAKED_DETAIL} refused")

        monkeypatch.setitem(views.READINESS_CHECKS, name, failing_check)

    return factory


@allure.feature("Платформа")
@allure.story("Служебные проверки")
class TestHealth:
    """Живость и готовность приложения.

    Тесты:
      1. /health/ отвечает 200 и не обращается к БД
      2. /ready/ отвечает 200, когда БД и кэш доступны
      3. /ready/ отвечает 503, называет упавший компонент и пишет причину в лог
      4. Текст ошибки не попадает в публичный ответ /ready/
      5. Служебные адреса открыты без входа и не кэшируются
    """

    # Без django_db намеренно: pytest-django уронит тест, если /health/ полезет в базу.
    @allure.title("/health/ отвечает без обращения к БД")
    def test_health_does_not_touch_database(self, client):
        response = client.get("/health/")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.django_db
    @allure.title("/ready/ отвечает 200, когда БД и кэш доступны")
    def test_ready_when_all_components_ok(self, client):
        response = client.get("/ready/")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "checks": {"database": "ok", "cache": "ok"},
        }

    @pytest.mark.django_db
    @pytest.mark.parametrize("component", COMPONENTS)
    @allure.title("/ready/ отвечает 503, если упал компонент {component}")
    def test_ready_reports_failed_component(self, client, caplog, break_component, component):
        break_component(component)

        with caplog.at_level(logging.ERROR, logger="core.health.views"):
            response = client.get("/ready/")

        assert response.status_code == 503
        checks = response.json()["checks"]
        assert checks.pop(component) == "fail"
        assert set(checks.values()) == {"ok"}, "остальные компоненты должны остаться ok"
        assert component in caplog.text
        assert LEAKED_DETAIL in caplog.text, "причина должна остаться в логе"

    @pytest.mark.django_db
    @allure.title("Текст ошибки не попадает в публичный ответ /ready/")
    def test_ready_does_not_leak_error_details(self, client, break_component):
        break_component("database")

        response = client.get("/ready/")

        assert LEAKED_DETAIL not in response.content.decode()

    @pytest.mark.django_db
    @pytest.mark.parametrize("url", SERVICE_URLS)
    @allure.title("{url} открыт без входа и не кэшируется")
    def test_service_url_is_public_and_not_cached(self, client, url):
        response = client.get(url)

        # Отметка login_not_required: после LoginRequiredMiddleware (#13) адрес останется публичным.
        assert resolve(url).func.login_required is False
        assert "no-store" in response["Cache-Control"]
