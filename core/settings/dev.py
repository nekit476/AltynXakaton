"""Локальная разработка: `uv run poe dev`."""

from core.settings.base import *  # noqa: F403
from core.settings.base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)
# Ключ для разработки генерирует bootstrap; запасной нужен, чтобы manage.py работал и без .env.
SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="django-insecure-dev-only")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])
INTERNAL_IPS = ["127.0.0.1"]
