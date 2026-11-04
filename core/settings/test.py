"""Настройки pytest (pyproject.toml → DJANGO_SETTINGS_MODULE).

База берётся из DATABASE_URL, но pytest-django создаёт рядом отдельную test_<имя>:
у каждого участника своя база, значит, и тестовые базы не пересекаются.
"""

from core.settings.base import *  # noqa: F403
from core.settings.components import cache_settings

SECRET_KEY = "test-only-secret-key"
DEBUG = False
ALLOWED_HOSTS = ["testserver"]

# Тесты не трогают общий Redis: ни кэш, ни очередь задач.
CACHES = cache_settings("")
CELERY_BROKER_URL = "memory://"
CELERY_TASK_ALWAYS_EAGER = True

# Быстрый хеш: в фабриках создаются сотни пользователей, а стойкость пароля тут не проверяется.
# Проверку настоящего хешера делают отдельные тесты входа (задача #12).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
