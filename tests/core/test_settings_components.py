"""Сборка настроек БД и кэша из строк подключения (core/settings/components.py)."""

import allure
import pytest
from django.core.exceptions import ImproperlyConfigured

from core.settings.components import (
    CACHE_KEY_PREFIX,
    DB_CONN_MAX_AGE_S,
    DB_CONNECT_TIMEOUT_S,
    POSTGRES_ENGINE,
    REDIS_SOCKET_TIMEOUT_S,
    cache_settings,
    database_settings,
)

LOCAL_URL = "postgres://dekanat:pw@127.0.0.1:5433/dekanat_a"
REMOTE_TLS_URL = "postgres://dekanat:pw@db.example.ru:5432/dekanat_b?sslmode=require"
REDIS_URL = "redis://:pw@127.0.0.1:6379/2"

NOT_POSTGRES_URLS = [
    pytest.param("sqlite:///db.sqlite3", id="sqlite"),
    pytest.param("mysql://user:pw@127.0.0.1:3306/dekanat", id="mysql"),
]


@allure.feature("Платформа")
@allure.story("Настройки подключения")
class TestDatabaseSettings:
    """DATABASES из DATABASE_URL: локальная и удалённая база без правки кода.

    Тесты:
      1. Хост, порт и имя базы берутся из URL — и локальные, и удалённые
      2. Параметры из query (sslmode) попадают в OPTIONS — TLS к удалённой БД настройкой
      3. Короткий таймаут подключения по умолчанию, явный из URL не перетирается
      4. Постоянные соединения с проверкой перед использованием
      5. Не-PostgreSQL отвергается понятной ошибкой
    """

    @allure.title("Хост, порт и база из URL")
    def test_connection_target_from_url(self):
        config = database_settings(REMOTE_TLS_URL)

        assert config["ENGINE"] == POSTGRES_ENGINE
        assert (config["HOST"], config["PORT"], config["NAME"]) == (
            "db.example.ru",
            5432,
            "dekanat_b",
        )

    @allure.title("sslmode из URL попадает в OPTIONS")
    def test_query_options_are_passed(self):
        config = database_settings(REMOTE_TLS_URL)

        assert config["OPTIONS"]["sslmode"] == "require"

    @allure.title("Таймаут подключения: по умолчанию короткий, явный сохраняется")
    def test_connect_timeout(self):
        default = database_settings(LOCAL_URL)
        explicit = database_settings(f"{LOCAL_URL}?connect_timeout=30")

        assert default["OPTIONS"]["connect_timeout"] == DB_CONNECT_TIMEOUT_S
        assert int(explicit["OPTIONS"]["connect_timeout"]) == 30

    @allure.title("Постоянные соединения с проверкой перед запросом")
    def test_persistent_connections_with_health_checks(self):
        config = database_settings(LOCAL_URL)

        assert config["CONN_MAX_AGE"] == DB_CONN_MAX_AGE_S
        assert config["CONN_HEALTH_CHECKS"] is True

    @pytest.mark.parametrize("url", NOT_POSTGRES_URLS)
    @allure.title("Не-PostgreSQL отвергается: {url}")
    def test_only_postgres_is_allowed(self, url):
        with pytest.raises(ImproperlyConfigured, match="только PostgreSQL"):
            database_settings(url)


@allure.feature("Платформа")
@allure.story("Настройки подключения")
class TestCacheSettings:
    """CACHES из REDIS_URL.

    Тесты:
      1. Без REDIS_URL — кэш в памяти процесса, общий Redis не нужен
      2. С REDIS_URL — Redis с префиксом ключей и короткими таймаутами
    """

    @allure.title("Без REDIS_URL кэш живёт в памяти процесса")
    def test_without_redis_uses_local_memory(self):
        cache = cache_settings("")["default"]

        assert cache["BACKEND"].endswith("LocMemCache")

    @allure.title("С REDIS_URL — Redis с префиксом и таймаутами")
    def test_with_redis(self):
        cache = cache_settings(REDIS_URL)["default"]

        assert cache["BACKEND"].endswith("RedisCache")
        assert cache["LOCATION"] == REDIS_URL
        assert cache["KEY_PREFIX"] == CACHE_KEY_PREFIX
        assert cache["OPTIONS"]["socket_connect_timeout"] == REDIS_SOCKET_TIMEOUT_S
        assert cache["OPTIONS"]["socket_timeout"] == REDIS_SOCKET_TIMEOUT_S
