"""Приложение Celery: фоновые задачи (PDF справок, уведомления) и Beat (напоминания).

Настройки берутся из Django-настроек с префиксом CELERY_ (см. core/settings/base.py).
Задачи из domain/*/tasks.py находятся автоматически.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.dev")

app = Celery("dekanat")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
