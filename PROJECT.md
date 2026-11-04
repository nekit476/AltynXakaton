# «Зачётка» — устройство проекта

Личный кабинет студента, преподавателя и администратора — концепт для конкурса «Цифровой деканат будущего».
Здесь описано, **как устроен код и как его запускать**. Что делаем и зачем — в [docs/plan/](docs/plan/README.md).

Стек: Python 3.13 · Django 5.2 LTS · HTMX · PostgreSQL 17 · Redis 7 · Celery · Docker Compose · uv.

---

## 1. Быстрый старт — одна команда

Нужен только git. Python, uv и все зависимости скрипт поставит сам.

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Dev b
```

**Linux / macOS / WSL:**

```bash
./scripts/setup.sh --dev b
```

`-Dev` / `--dev` — буква участника: `a` — Никита (core), `b` — учебная логика (domain), `c` — интерфейс (web).
Без неё скрипт спросит сам.

Что делает скрипт (повторный запуск безопасен):

1. Ставит [uv](https://docs.astral.sh/uv/), если его нет.
2. `uv sync --locked`: скачивает Python 3.13 (системный Python не нужен и не трогается) и ставит **все** зависимости из `uv.lock` в `.venv/`. Версии у всех одинаковые.
3. `scripts/bootstrap.py`:
   - создаёт `.env` с **твоей** базой, индексом Redis и случайным `SECRET_KEY`;
   - ставит git-хуки pre-commit;
   - проверяет связь с БД и подсказывает, что делать, если её нет.

Дальше:

```bash
uv run poe migrate
```

```bash
uv run poe dev
```

Открыть http://127.0.0.1:8000. Список всех команд — `uv run poe`.

---

## 2. Четыре модуля

Код разделён по участникам: у каждого своя папка, и в чужую без согласования не заходим.

| Модуль | Участник | Что внутри | Зона в тестах |
|---|---|---|---|
| **`core/`** | 1 — A «Платформа и качество» (Никита) | Настройки, `User` и роли, права (`require_perm`), вход, аудит, экраны админа, `/health/` `/ready/`, общая иерархия ошибок | `tests/core/` |
| **`domain/`** | 2 — B «Учебная логика» | Модели, менеджеры, сервисы, селекторы, формы, задачи Celery, сидер | `tests/domain/` |
| **`web/`** | 3 — C «Интерфейс и продукт» | Views и URL, шаблоны, HTMX-фрагменты, компоненты `ui/`, статика, Tailwind | `tests/web/` |
| **`tests/`** | все, каркас — A | Тесты всех модулей, сторож границ, E2E (Playwright), нагрузка (k6) | — |

Инфраструктура (`infra/`, `scripts/`, `Dockerfile`, `pyproject.toml`, CI) — зона A.

### Дерево

```text
dekanat/
├─ PROJECT.md · README.md · CLAUDE.md
├─ pyproject.toml · uv.lock · .python-version   зависимости, команды poe, настройки ruff/pytest
├─ manage.py · .env.example · Dockerfile · .pre-commit-config.yaml
│
├─ core/                     ── участник 1 (A)
│  ├─ settings/              base · dev · test · prod · components (БД и кэш из URL)
│  ├─ urls.py · wsgi.py · celery.py · errors.py (AppError → NotFound)
│  ├─ users/                 своя модель User: UUID, роль, отчество (AUTH_USER_MODEL)
│  └─ health/                /health/ и /ready/
│                            дальше: access/ (#13) · accounts/ (#12) · audit/ (#26) · adminpanel/ (#25)
├─ domain/                   ── участник 2 (B)
│  └─ org · schedule · courses · assignments · grades · requests · notifications · seed
│                            в каждом: models · managers · services · selectors · forms · tasks
├─ web/                      ── участник 3 (C)
│  ├─ views.py · urls.py
│  ├─ templates/             base.html · web/ · дальше ui/ и <раздел>/_partials/
│  └─ static/                css/ · дальше js/ и vendor/
├─ tests/                    ── модуль тестов
│  ├─ core/ · domain/ · web/ тесты по модулям кода
│  ├─ test_architecture.py   сторож границ модулей
│  ├─ e2e/                   Playwright (#28, #67)
│  └─ load/                  k6 (#42)
├─ infra/                    compose.yml · postgres/initdb/
├─ scripts/                  setup.ps1 · setup.sh · bootstrap.py
├─ docs/                     plan/ · tz/ · plans/ · prompts.md
└─ tracker/                  Excel-трекеры и их генератор
```

### Как модули зависят друг от друга

```text
web ──► domain (services · selectors · forms) ──► core
 └────────────────────────────────────────────► core (require_perm, ошибки)
```

- **`domain` не знает о `web`.** Сервисы не возвращают HTML и не импортируют views.
- **`web` не лезет в модели.** View вызывает сервис или селектор и получает DTO (`@dataclass(frozen=True)`). Импорт `domain.<app>.models` или `.managers` из `web/` запрещён: так все чтения идут через селекторы с областью видимости (`for_student`), и студент не получает чужой queryset.
- **Ошибки — из `core.errors`.** Сервис бросает `NotFound`, view ловит `AppError` и отдаёт 404.

Правила проверяет тест `tests/test_architecture.py`. Он же падает, если появилось приложение, не подключённое в `INSTALLED_APPS`.

### Новое приложение в domain/

1. Папка `domain/<имя>/` с `__init__.py` и `apps.py`: `name = "domain.<имя>"`, `label = "<имя>"`.
2. Строка в `DOMAIN_APPS` в `core/settings/base.py`. Забудешь — упадёт сторож.
3. Модели → `uv run poe makemigrations` → `uv run poe check`.

---

## 3. Окружение и зависимости

- **uv** управляет Python и зависимостями. Версия Python закреплена в `.python-version`, точные версии пакетов — в `uv.lock` (коммитится).
- Добавить зависимость: `uv add <пакет>`, для разработки — `uv add --dev <пакет>`. Потом коммитим `pyproject.toml` и `uv.lock` вместе.
- Обновить окружение после чужого коммита: `uv sync`.
- Активировать `.venv` не обязательно: `uv run <команда>` сам берёт нужное окружение.

### Команды (`uv run poe <команда>`)

| Команда | Что делает |
|---|---|
| `setup` | `.env`, git-хуки, проверка БД (то же, что в конце setup-скрипта) |
| `dev` | Сервер разработки на http://127.0.0.1:8000 |
| `migrate` · `makemigrations` | Миграции |
| `superuser` | Командный аккаунт для Django admin (путь — `DJANGO_ADMIN_PATH`, по умолчанию `/team-admin/`) |
| `shell` | Django shell |
| `test` | Все тесты; аргументы пробрасываются: `uv run poe test -k users` |
| `lint` | ruff check, ruff format --check, djlint — как в CI |
| `fmt` | Отформатировать код и шаблоны |
| `check` | `manage.py check` и `makemigrations --check` |
| `worker` · `beat` | Celery-воркер и планировщик (нужен Redis) |
| `db-check` | Проверить связь с БД из `DATABASE_URL` |
| `db-up` · `db-down` · `db-logs` · `db-psql` | Сервер PostgreSQL + Redis в Docker |
| `app-up` · `app-down` | Весь стенд в Docker: БД, Redis, web, worker, beat на http://127.0.0.1:8080 |

Make на Windows из коробки нет, а poe одинаково работает на Windows, Linux и в CI.

---

## 4. База данных и Redis

### Схема

```text
             один сервер (Docker: postgres:17 + redis:7)
             ┌───────────────────────────────────────────┐
участник a ─►│ dekanat_a   test_dekanat_a    redis db 1  │
участник b ─►│ dekanat_b   test_dekanat_b    redis db 2  │
участник c ─►│ dekanat_c   test_dekanat_c    redis db 3  │
стенд app  ─►│ dekanat                       redis db 0  │
             └───────────────────────────────────────────┘
```

**Сервер общий, база у каждого своя.** Локально ставить PostgreSQL не нужно, а миграции из незаконченной ветки одного не ломают базу другого.
Тестовая база pytest — `test_<имя твоей базы>` рядом с твоей, поэтому одновременные прогоны у троих не пересекаются.
Базы участников создаёт `infra/postgres/initdb/10-dev-databases.sh` при первом запуске тома (список — `DEV_DATABASES`).

### Сейчас: сервер у Никиты

```bash
uv run poe db-up
```

Нужен Docker Desktop. PostgreSQL слушает `127.0.0.1:5433`: порт 5432 часто занят PostgreSQL, установленным прямо в систему (у Никиты так и есть), Redis — `127.0.0.1:6379`.
Оба порта открыты только на этой машине.

### Скоро: сервер на VPS — код не меняется

На сервере запускается тот же `infra/compose.yml`, порты так же слушают только `127.0.0.1`: БД наружу не открываем ([03_security.md](docs/plan/03_security.md) §8).
Каждый подключается через SSH-туннель:

```bash
ssh -N -L 5433:127.0.0.1:5433 -L 6379:127.0.0.1:6379 dev@<адрес-сервера>
```

Пока туннель открыт, удалённая БД для приложения выглядит локальной, и **`.env` остаётся тем же**.

Если нужен прямой доступ без туннеля, достаточно поменять строку в `.env`, код не трогается:

```text
DATABASE_URL=postgres://dekanat:<пароль>@db.example.ru:5432/dekanat_b?sslmode=require
```

### Что заложено в код под удалённую БД

| Что | Где | Зачем |
|---|---|---|
| Подключение только из `DATABASE_URL`, параметры из query-строки (`sslmode`, `connect_timeout`) идут в `OPTIONS` | `core/settings/components.py` | Переезд и TLS — правка `.env`, а не кода |
| `connect_timeout = 5 с` | там же | Недоступный сервер не подвешивает поток на ~2 минуты |
| `CONN_MAX_AGE = 60`, `CONN_HEALTH_CHECKS` | там же | Не платим за TCP и авторизацию на каждый запрос; оборванное соединение проверяется заранее |
| Только PostgreSQL | там же | На SQLite модели с JSONB и массивами не мигрируют, поэтому сразу понятная ошибка |
| Таймауты Redis 2 с, префикс ключей `dekanat` | там же | Общий Redis не смешивает ключи разных окружений |
| `/ready/` показывает, что именно упало | `core/health/` | `{"checks": {"database": "ok", "cache": "fail"}}` |
| `uv run poe db-check` | `scripts/bootstrap.py` | Проверить связь до запуска сервера |

### Без Redis

`REDIS_URL=` (пусто): кэш живёт в памяти процесса, а задачи Celery выполняются сразу, без воркера.
Так можно работать, пока до Redis нет доступа. Тесты всегда идут в этом режиме и общий Redis не трогают.

---

## 5. Docker

| Файл | Что внутри |
|---|---|
| `Dockerfile` | Один образ для web, worker и beat. Python 3.13-slim, зависимости через uv из `uv.lock`, `collectstatic`, пользователь не root, gunicorn gthread. Параметры gunicorn задаются через `GUNICORN_CMD_ARGS`. |
| `infra/compose.yml` | `postgres` и `redis` запускаются всегда. `web`, `worker` и `beat` — только с профилем `app`. Порты слушают `127.0.0.1`. Тома: `pgdata`, `redisdata`, `files`. |
| `infra/postgres/initdb/` | Создание баз участников при первом запуске. |

Прод-конфигурация (Caddy с HTTPS, лимиты памяти, `deploy.sh`) — задачи #5 и #15.

---

## 6. Настройки (`.env`)

Шаблон — `.env.example`. Настоящий `.env` создаёт bootstrap, в git он не попадает.

| Переменная | Кому нужна | Смысл |
|---|---|---|
| `DATABASE_URL` | всем | Своя база: `.../dekanat_<буква>` |
| `REDIS_URL` | всем (можно пусто) | Свой индекс: `.../<1\|2\|3>` |
| `DJANGO_SECRET_KEY` | всем | Генерируется bootstrap |
| `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_ADMIN_PATH` | всем | Режим, хосты, путь к Django admin |
| `DEV_PARTICIPANT` | всем | Буква участника, для справки |
| `POSTGRES_*`, `REDIS_PASSWORD`, `*_BIND`, `*_PORT`, `DEV_DATABASES` | только тому, кто держит сервер БД | Параметры контейнеров |

Настройки по окружениям: `core.settings.dev` (manage.py), `test` (pytest), `prod` (образ).

---

## 7. Что уже подключено

| Интеграция | Состояние |
|---|---|
| PostgreSQL (psycopg 3) | ✓ через `DATABASE_URL`, база на участника |
| Redis: кэш и сессии `cached_db` | ✓, без Redis — режим в памяти |
| Celery + Beat (брокер Redis) | ✓ приложение `core/celery.py`, задачи из `domain/*/tasks.py` находятся сами; без Redis — eager |
| django-htmx | ✓ `request.htmx` во всех views |
| WhiteNoise | ✓ статика без отдельного веб-сервера, в проде — сжатые файлы с хешем в имени |
| Своя модель `User` | ✓ в первой миграции: UUID, роль, отчество |
| Django admin на секретном пути | ✓ `DJANGO_ADMIN_PATH` |
| pytest + pytest-django + Allure + factory_boy | ✓ тесты каркаса и сторож границ модулей |
| ruff, djlint, pre-commit | ✓ |
| Docker: образ, compose, initdb | ✓ написано, ждёт Docker Desktop для проверки |

Дальше по [бэклогу](docs/plan/07_backlog.md): CI (#4), VPS и Caddy (#5), вход и argon2 (#12), права и `require_perm` (#13), Tailwind и HTMX на фронте (#19).

---

## 8. Расхождения с планом

Изменения относительно [02_architecture.md](docs/plan/02_architecture.md) §6 и таблицы «Зона кода» в [06_team_roadmap.md](docs/plan/06_team_roadmap.md). План в этих местах ещё не обновлён.

| В плане | Сделано | Почему |
|---|---|---|
| `apps/<app>/` общие для B и C: в одной папке models (B) и views (C) | Четыре модуля `core/`, `domain/`, `web/`, `tests/` | Решение 04.11: у каждого участника своя папка, меньше конфликтов при слиянии. Контракт B ↔ C (сервисы и DTO) теперь граница модулей, и её проверяет сторож импортов. |
| `config/` (settings, urls, celery) | `core/settings/`, `core/urls.py`, `core/celery.py` | Всё, что принадлежит A, лежит в одном модуле |
| `apps/core`, `apps/accounts`, `apps/adminpanel` | `core/users`, `core/health`; дальше `core/access`, `core/accounts`, `core/audit`, `core/adminpanel` | То же |
| `templates/`, `static/` в корне | `web/templates/`, `web/static/` | Вся зона C — в `web/` |
| Тесты в `apps/*/tests/` плюс `tests/authz`, `tests/e2e`; `load/` в корне | Всё в `tests/`: `core/`, `domain/`, `web/`, `e2e/`, `load/` | Отдельный модуль тестов |
| `make dev`, `make test`, `make lint` | `uv run poe dev/test/lint` | make на Windows из коробки нет |
| PostgreSQL на 5432 | В Docker — 5433 | 5432 занят системным PostgreSQL |
