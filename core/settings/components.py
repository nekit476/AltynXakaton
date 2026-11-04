"""Части настроек, которые собираются из строк подключения.

Вынесены в функции, чтобы принятые решения — только PostgreSQL, короткие таймауты к
удалённой БД, режим без Redis — проверялись тестами, а не только чтением base.py.
"""

from typing import Any

import environ
from django.core.exceptions import ImproperlyConfigured

POSTGRES_ENGINE = "django.db.backends.postgresql"

# БД скоро переедет на удалённый сервер. Без таймаута недоступный хост держит поток
# gunicorn на системный TCP-таймаут (~2 мин); 5 с хватает и для медленного канала.
DB_CONNECT_TIMEOUT_S = 5
# Постоянные соединения (04_infra.md §5): не платим за TCP + TLS + авторизацию на каждый запрос.
DB_CONN_MAX_AGE_S = 60

# Redis тоже может оказаться удалённым: не ждём его дольше, чем БД.
REDIS_SOCKET_TIMEOUT_S = 2
# Общий сервер Redis делят несколько окружений — префикс отделяет ключи проекта.
CACHE_KEY_PREFIX = "dekanat"


def database_settings(url: str) -> dict[str, Any]:
    """Строит DATABASES["default"] из DATABASE_URL.

    Параметры из query-строки URL (например, `?sslmode=require`) попадают в OPTIONS —
    так подключение к удалённой БД с TLS настраивается без правки кода.
    """
    config = environ.Env.db_url_config(url)
    if config["ENGINE"] != POSTGRES_ENGINE:
        # Проект опирается на возможности PostgreSQL (JSONB, массивы, полнотекстовый поиск):
        # на SQLite часть моделей просто не мигрирует, поэтому падаем сразу и понятно.
        raise ImproperlyConfigured(
            f"Поддерживается только PostgreSQL, а в DATABASE_URL движок {config['ENGINE']}"
        )
    options = config.setdefault("OPTIONS", {})
    options.setdefault("connect_timeout", DB_CONNECT_TIMEOUT_S)
    config["CONN_MAX_AGE"] = DB_CONN_MAX_AGE_S
    # После обрыва сети постоянное соединение проверяется перед запросом, а не падает на нём.
    config["CONN_HEALTH_CHECKS"] = True
    return config


def cache_settings(redis_url: str) -> dict[str, Any]:
    """Строит CACHES: Redis, если задан REDIS_URL, иначе кэш в памяти процесса.

    Режим без Redis нужен, чтобы разработчик и тесты не зависели от общего Redis:
    тесты не должны читать и писать чужие ключи.
    """
    if not redis_url:
        return {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    return {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": redis_url,
            "KEY_PREFIX": CACHE_KEY_PREFIX,
            "OPTIONS": {
                "socket_connect_timeout": REDIS_SOCKET_TIMEOUT_S,
                "socket_timeout": REDIS_SOCKET_TIMEOUT_S,
            },
        }
    }
