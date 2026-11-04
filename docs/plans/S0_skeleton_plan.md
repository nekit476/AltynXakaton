# План реализации. Этап `S0_skeleton`

Составлен на основе [S0_skeleton_tz.md](../tz/S0_skeleton_tz.md).

## Шаг 1. Окружение

**Файлы:** `pyproject.toml`, `.python-version`, `uv.lock`, `.gitignore`, `.gitattributes`, `.env.example`.
Зависимости: django 5.2, psycopg, django-environ, redis, celery, django-htmx, whitenoise, gunicorn (кроме Windows).
Dev-группа: pytest, pytest-django, factory-boy, allure-pytest, ruff, djlint, pre-commit, poethepoet, openpyxl (для трекера).
Задачи poe: `setup dev migrate makemigrations superuser shell worker beat test lint fmt check db-* app-*`.

## Шаг 2. Установка одной командой

**Файлы:** `scripts/setup.ps1`, `scripts/setup.sh`, `scripts/bootstrap.py`.
Оболочки ставят uv и выполняют `uv sync --locked`. Bootstrap собирает `.env` функцией `render_env` (база, индекс Redis и ключ участника), ставит pre-commit и проверяет БД через psycopg с таймаутом 3 с.

## Шаг 3. Модуль core

`settings/components.py`: `database_settings(url)` и `cache_settings(redis_url)`.
`settings/base.py`: списки `CORE_APPS`, `DOMAIN_APPS`, `WEB_APPS`. Плюс `AUTH_USER_MODEL`, сессии `cached_db`, Celery, WhiteNoise, django-htmx.
`users/`: `User(AbstractUser)` с UUID, `role`, `patronymic`, менеджер ставит суперпользователю роль админа. Миграция `0001_initial`.
`health/`: `READINESS_CHECKS = {database, cache}`, `run_check` переводит исключение в `fail` и пишет его в лог.

## Шаг 4. Модули domain и web

`domain/<app>/__init__.py` + `apps.py` для `org schedule courses assignments grades requests notifications seed`.
`web/`: view `home`, `base.html` с плашкой и `noindex`, `web/home.html`, временный `app.css`.

## Шаг 5. Тесты

`tests/core/` (users, health, settings_components, errors, bootstrap), `tests/web/test_home.py`, `tests/test_architecture.py`.

## Шаг 6. Docker

`Dockerfile`: python:3.13-slim, uv из образа `ghcr.io/astral-sh/uv:0.13`, `collectstatic`, пользователь `app`, параметры gunicorn в `GUNICORN_CMD_ARGS`.
`infra/compose.yml`: postgres:17 и redis:7 запускаются всегда, web, worker и beat — в профиле `app`.
`infra/postgres/initdb/10-dev-databases.sh`: базы участников.

## Шаг 7. Документы

`PROJECT.md`, `README.md`, `CLAUDE.md` в корне и в каждом модуле, этот ТЗ и план, `docs/prompts.md`.

## Шаг 8. Проверка и фиксация

`uv run poe test`, `uv run poe lint`, `uv run poe check`, запуск `uv run poe dev`, проверка `/`, `/ready/` и `/team-admin/`.
`git init`, первый коммит.

## Что этот этап НЕ меняет

- `docs/plan/*` и `tracker/*`. Расхождения структуры с 02_architecture.md §6 описаны в PROJECT.md §8, сам план правится отдельно.
- Модели предметной области: заготовки приложений `domain/` пустые, модели пишет B (#6).
- Вход, права, CSP и прод-настройки безопасности (#12, #13, #27).
- CI и деплой (#4, #15).
