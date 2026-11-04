# «Зачётка» — цифровой деканат будущего

Личный кабинет студента, преподавателя и администратора. Концепт для конкурса «Цифровой деканат будущего»: данные вымышленные, это не официальный сервис вуза.

Django 5.2 · HTMX · PostgreSQL · Redis · Celery · Docker.

## Запуск

```bash
git clone https://github.com/nekit476/AltynXakaton.git
cd AltynXakaton
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Dev a
```

Linux / macOS:

```bash
./scripts/setup.sh --dev a
```

```bash
uv run poe migrate
```

```bash
uv run poe dev
```

Сервер — http://127.0.0.1:8000, список команд — `uv run poe`.

## Как вносить изменения

Ветка `<буква>/<id>-<кратко>` от `main` → коммиты → pull request на GitHub. В `main` попадает только через PR.

## Документы

- [PROJECT.md](PROJECT.md) — устройство проекта: модули, команды, БД, Docker, настройки.
- [docs/plan/](docs/plan/README.md) — продукт, архитектура, безопасность, инфраструктура, качество, роадмап, бэклог.
- [CLAUDE.md](CLAUDE.md) — правила для ИИ-агентов.
