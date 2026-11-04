"""Корневая карта URL: служебные адреса, Django admin и интерфейс из web/.

Разделы интерфейса (студент, преподаватель, админ) подключаются в web/urls.py —
сюда новые строки добавляются только для модулей участника A.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path(settings.DJANGO_ADMIN_PATH, admin.site.urls),
    path("", include("core.health.urls")),
    path("", include("web.urls")),
]
