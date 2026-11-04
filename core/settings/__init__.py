"""Настройки по окружениям: base (общие) → dev / test / prod.

Выбор — переменной DJANGO_SETTINGS_MODULE: manage.py по умолчанию берёт dev,
pytest — test (pyproject.toml), gunicorn в образе — prod.
"""
