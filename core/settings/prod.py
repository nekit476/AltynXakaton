"""Прод и staging: образ Docker за Caddy.

Здесь только то, без чего прод нельзя запускать. Заголовки, CSP, cookie `__Host-`,
argon2 и axes добавляются задачами #12 и #27 (03_security.md).
"""

from core.settings.base import *  # noqa: F403
from core.settings.base import env

DEBUG = False
# Без значения по умолчанию: прод без своего ключа и списка хостов не стартует.
SECRET_KEY = env.str("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# TLS снимает Caddy; о том, что запрос пришёл по HTTPS, он сообщает этим заголовком.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS и редирект http → https ставит Caddy для всего сайта (03_security.md §5), а не Django:
# так они действуют и на ответы, которые Django не обрабатывает (статика, файлы через X-Accel).
# Без этого `check --deploy --fail-level WARNING` в CI падал бы на W004 и W008.
SILENCED_SYSTEM_CHECKS = ["security.W004", "security.W008"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Имена с хешем содержимого → вечный кэш в браузере, сжатие gzip/brotli заранее.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
