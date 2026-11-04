"""Модуль участника 1 (A, «Платформа и качество»): настройки, пользователи, права, служебные URL.

Импорт Celery здесь — чтобы приложение Celery поднималось вместе с Django и
`@shared_task` из domain/ регистрировались в нём.
"""

from core.celery import app as celery_app

__all__ = ("celery_app",)
