# CLAUDE.md — «Зачётка»

Общий контекст для Claude Code каждого участника. Как устроен код и как запускать — [PROJECT.md](PROJECT.md).
Что делаем и зачем — [docs/plan/](docs/plan/README.md). Стек: Django 5.2 + HTMX, PostgreSQL, Redis, Celery.

## Модули и зоны

| Папка | Владелец | Правила модуля |
|---|---|---|
| `core/` | участник 1 — A (Никита) | [core/CLAUDE.md](core/CLAUDE.md) |
| `domain/` | участник 2 — B | [domain/CLAUDE.md](domain/CLAUDE.md) |
| `web/` | участник 3 — C | [web/CLAUDE.md](web/CLAUDE.md) |
| `tests/` | `tests/<модуль>/` — владелец модуля; остальное — A | [tests/CLAUDE.md](tests/CLAUDE.md) |
| `infra/`, `scripts/`, `Dockerfile`, `pyproject.toml`, `.github/` | A | — |

Работай только в зоне того, кто ставит задачу. Если нужна правка в чужой зоне, не делай её, а назови отдельной строкой в ответе.

## Зависимости между модулями

`web → domain (services, selectors, forms) → core`. `domain` не импортирует `web`. `web` не импортирует `domain.*.models` и `domain.*.managers`.
Это проверяет `tests/test_architecture.py`.

## Команды

```bash
uv run poe dev          # сервер http://127.0.0.1:8000
uv run poe test         # pytest
uv run poe lint         # ruff + djlint
uv run poe fmt          # форматирование
uv run poe check        # manage.py check + makemigrations --check
uv run poe makemigrations
uv add <пакет>          # зависимость; uv add --dev <пакет> — для разработки
```

## Нельзя нарушать

Подробно — в [03_security.md](docs/plan/03_security.md).

- У каждого view есть `@require_perm(...)` (появится в задаче #13). Публичные views помечены `@login_not_required` и внесены в `PUBLIC_VIEWS`.
- Данные читаются только через селекторы и менеджеры с областью видимости (`for_student`, `for_teacher`). Чужой объект даёт `NotFound` → 404, а не 403.
- Формы с явным `fields = [...]`, никогда `__all__`.
- Никаких `|safe`, `mark_safe`, `raw()`, `extra()`, inline-скриптов и `hx-on`.
- Задачи Celery ставятся только через `transaction.on_commit` и должны быть идемпотентными.
- `.env*` не читать и не писать. Секреты берутся только из переменных окружения.
- Данные только вымышленные.
- Схема меняется только миграциями: после правки моделей — `makemigrations`, затем `uv run poe check`.

## Процесс

- ТЗ → план → реализация: `docs/tz/<этап>_<задача>_tz.md`, `docs/plans/<этап>_<задача>_plan.md`. В плане обязателен раздел «Что этот этап НЕ меняет».
- Ключевые промпты и то, что пришлось возвращать на доработку, записываются в `docs/prompts.md`.
- Перед словом «готово» должны пройти `uv run poe test`, `uv run poe lint` и `uv run poe check`. Если что-то упало, покажи вывод.
- Ветка `<буква>/<id>-<кратко>` от свежего `main` (например `b/43-reschedule`), коммит `feat(schedule): перенос пары с проверкой конфликтов (#43)`.
- Репозиторий — https://github.com/nekit476/AltynXakaton. В `main` попадает только через pull request на GitHub: локально в `main` не сливать и `main` не пушить.
- Definition of Done — [05_quality.md](docs/plan/05_quality.md) §5.
