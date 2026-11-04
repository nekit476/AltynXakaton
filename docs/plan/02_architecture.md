# 02. Архитектура и стек

**Решение (04.11):** монолит на Django. Сервер отдаёт готовый HTML, интерактивность даёт HTMX, весь код на Python.
Фоновые задачи выполняет Celery, брокером служит Redis. Отдельного фронтенда на JS и отдельного брокера сообщений нет.

## 1. Стек

| Слой | Выбор | Зачем |
|---|---|---|
| Ядро | **Python 3.13, Django 5.2 LTS** | Вход, сессии, CSRF, формы, права, миграции и ORM есть из коробки, поэтому три человека за 19 дней не пишут это сами. LTS поддерживается до 2028 года. |
| Сервер приложений | **gunicorn** (`gthread`, 6 воркеров × 4 потока) | Простая и проверенная схема для синхронного Django. Число параллельных хешей argon2 ограничено самим числом потоков. |
| Интерфейс | **Django-шаблоны + HTMX 2 (django-htmx)** | Сервер возвращает фрагменты HTML, и HTMX подменяет часть страницы без перезагрузки: сдал ДЗ — обновился только блок статуса. JS почти не пишем. |
| Мелкая интерактивность | **Alpine.js (CSP-сборка)**, **SortableJS** | Выпадающие меню, модалки, перетаскивание разделов в конструкторе. Только CSP-сборка Alpine: обычная требует `unsafe-eval`. |
| Стили | **Tailwind CSS 4 (standalone CLI)** | Современный вид. Утилита собирает CSS без Node. Компоненты лежат как Django-шаблоны в `web/templates/ui/`. |
| Графики в админке | **Chart.js** (MIT) | Статистика для админа, статичный файл без сборки. |
| БД | **PostgreSQL 17** | Реляционные данные, транзакции, полнотекстовый поиск по-русски для глобального поиска. |
| Кэш, сессии, брокер | **Redis 7** (AOF включён) | Кэш расписания по группам, хранилище сессий (`cached_db`), счётчики уведомлений, лимиты, брокер Celery. |
| Фоновые задачи | **Celery 5 + Celery Beat** | Напоминания о дедлайнах, PDF справок, рассылка уведомлений, «автоноль». Задачи ставятся только после коммита транзакции. |
| PDF справок | **WeasyPrint + segno (QR)** | HTML-шаблон превращается в PDF с кириллицей, QR ведёт на страницу проверки. |
| Пароли | **argon2id** (`argon2-cffi`, свой хешер с m = 19 МиБ) | Рекомендация OWASP. Параметры Django по умолчанию слишком тяжёлые, см. [03_security.md](03_security.md). |
| Защита входа | **django-axes** | Блокировка перебора по логину, а не по IP: в вузовском Wi-Fi все сидят за одним NAT. |
| CSP | **django-csp** | Content-Security-Policy. В Django 5.2 своей поддержки CSP ещё нет. |
| Статика | **WhiteNoise** (сжатые файлы с хешем в имени) | Django сам отдаёт статику с вечным кэшем, отдельный том и nginx не нужны. |
| Веб-сервер | **Caddy 2** | Автоматический HTTPS, заголовки, лимит и **буферизация** тела запроса, защищённая отдача файлов ДЗ через `X-Accel-Redirect`. |
| Контейнеры | **Docker Compose** | Весь стенд одной командой и локально, и на VPS. |
| CI/CD | **GitHub Actions + GHCR** | Тесты на каждый PR, сборка одного образа, деплой по SSH. |
| Мониторинг | **Prometheus + Grafana** (django-prometheus) | Графики во время нагрузочных тестов. Отдельный профиль compose. |
| Тесты | pytest-django, factory_boy, hypothesis, **Playwright (Python)**, k6, OWASP ZAP | Тесты тоже на Python, даже E2E. Подробно в [05_quality.md](05_quality.md). |
| Окружение и команды | **uv** (Python 3.13 и зависимости из `uv.lock`), **poethepoet** (`uv run poe <команда>`) | Установка одной командой `scripts/setup.ps1` на любой машине, одинаковые версии у всех. Команды одинаково работают на Windows и Linux. |

### Отвергнутые варианты

| Вариант | Почему нет |
|---|---|
| FastAPI + React (SPA) | Первая версия плана. Два языка, два процесса сборки и контракт OpenAPI между ними. Вход, сессии, CSRF и админку пришлось бы писать самим. Для кабинета за логином SPA ничего не добавляет. |
| FastAPI + Jinja2 + HTMX | Тот же монолит, но без встроенных входа, форм, прав и миграций. Сэкономленное на «лёгкости» время уйдёт на велосипеды. |
| NiceGUI / Reflex / Flet | UI целиком на Python, но состояние каждой вкладки живёт на сервере в своём WebSocket. 3 000 одновременных студентов дают 3 000 соединений и состояний в памяти, для горизонтального масштабирования нужны sticky-сессии. Вёрстку под телефон контролируешь хуже. Reflex к тому же внутри собирает React и требует Node. |
| Streamlit | Инструмент для дашбордов аналитика, а не многопользовательский кабинет. |
| RabbitMQ (или Kafka) | Для сдачи ДЗ брокер не нужен: это синхронный запрос, ответ «Сдано» нужен сразу. Для фоновых задач хватает Redis, который уже стоит. RabbitMQ — ещё один сервис (~200–300 МБ RAM, пароли, мониторинг), а его гарантии доставки при 15 тыс. пользователей не нужны. Перейти на него можно позже одной строкой `CELERY_BROKER_URL`. |
| Файлы ДЗ через очередь | Сообщения в брокере должны быть маленькими. Файл кладётся в хранилище, а в задачу передаётся только его ID. |
| ASGI (uvicorn) + async Django | Асинхронность нужна для тысяч долгих соединений (WebSocket, стриминг), у нас их нет. Синхронный ORM проще и надёжнее. Медленные загрузки с телефона снимает буферизация в Caddy. |
| Отдача статики через Caddy | Работает, но нужен общий том между контейнерами. WhiteNoise с хешированными именами и вечным кэшем для нас не хуже. |
| MinIO для файлов | Лишний контейнер. Локальный том спрятан за `Storage` из Django, S3 (Yandex Object Storage / Selectel) подключается настройкой `STORAGES`. |
| Kubernetes, Cloudflare | Как и раньше: k8s на одном VPS избыточен, а Cloudflare — риск доступа из РФ без VPN. |
| Общие для B и C папки `apps/<app>/` (models у B, views у C рядом) | Первая версия структуры. B и C правили бы одни и те же папки, и при слиянии были бы конфликты, а граница контракта была видна только на ревью. С 04.11 код разделён на модули по участникам (п. 6), и границу проверяет тест. |
| Makefile | На Windows make из коробки нет, а вся команда на Windows. Команды — задачи poe в `pyproject.toml`. |
| Локальный PostgreSQL у каждого | Три установки и три версии. Вместо этого один сервер в Docker и своя база у каждого участника (п. 6). |

## 2. Контейнеры

```
                 Интернет (443)
                      │
               ┌──────▼──────┐
               │    caddy    │  HTTPS · заголовки · лимит 25 МБ · буферизация тела
               └──────┬──────┘  · X-Accel-Redirect → том files/ (отдача ДЗ после проверки прав)
                      │
               ┌──────▼──────┐
               │     web     │  Django: страницы + HTMX-фрагменты + статика (WhiteNoise)
               └──┬───────┬──┘  gunicorn gthread 6×4
                  │       │ on_commit → задача
      ┌───────────▼┐   ┌──▼────────┐     ┌──────────┐
      │  postgres  │   │   redis   │◄────┤  worker  │  Celery: PDF, уведомления
      └─────▲──────┘   └─────▲─────┘     └──────────┘
            │                │           ┌──────────┐
            └────────────────┴───────────┤   beat   │  напоминания каждые 5 мин
                                         └──────────┘
   web, worker, beat — ОДИН образ, разная команда запуска
   тома: pgdata/, files/, backups/      профиль monitoring: prometheus, grafana, exporters
```

- Наружу открыты только 80 и 443 у `caddy`.
- Отдельного фронтенд-контейнера и сборки на Node нет: Tailwind собирается внутри Docker-образа утилитой standalone CLI.
- Расчёт памяти и CPU — в [04_infra.md](04_infra.md).

### Как проходит сдача ДЗ

1. Студент отправляет форму с файлом (`hx-post`). Caddy буферизует тело запроса, поэтому медленный мобильный интернет не держит воркер.
2. `web` проверяет права (студент записан на курс, задание открыто по политике), расширение, сигнатуру и размер.
3. В одной транзакции файл сохраняется в `files/`, а в БД появляется запись `Submission`.
4. Ответ — HTML-фрагмент «Сдано 14:32, попытка 1 из 3», HTMX подменяет блок статуса. Всё вместе занимает ~100–300 мс.
5. `transaction.on_commit(...)` ставит задачу в Redis. Если поставить её раньше, воркер может не найти запись.
6. `worker` уведомляет преподавателя. Задача идемпотентна: повтор не создаст второе уведомление.

## 3. Модель данных (ядро)

Без изменений по сравнению с первой версией. Модели живут в Django-приложениях модуля `domain/` (п. 6), `users` — в `core/users/`.

```
faculties ─< directions ─< groups ─< students >─ users (кастомный User: role, is_active)
departments ─< teachers >─ users
semesters (year, term, start, end, is_current)
disciplines
curriculum_items (direction, enrollment_year, semester_no, discipline, hours_*, control_form, credits)

courses (discipline, semester) ─< course_groups >─ groups
        ─< course_teachers >─ teachers (role: лектор / семинарист)
        ─< course_sections (title, kind: materials|assignment|announcement, position, is_visible)
               ─< materials (type: file|link|text, title, body_md, file)
               ─< assignments (max_score, opens_at, deadline_at, hard_deadline_at,
                               late_policy: reject|mark|penalty|auto_zero, penalty_pct_per_day,
                               allowed_ext[], max_file_mb, max_attempts)
                      ─< deadline_changes (old, new, reason, changed_by, at)
                      ─< deadline_extensions (student, new_deadline)
                      ─< submissions (student, attempt, submitted_at, is_late, status,
                                      score_raw, score_final, feedback, graded_by)
                             ─< submission_files (file, original_name, mime, size, sha256)

time_slots (pair_no, start, end)   rooms (building, number, capacity)
lessons (course, teacher, room, date, slot, type, status: normal|moved|cancelled)
   ─< lesson_groups >─ groups
   ─< lesson_changes (old_date, old_slot, old_room, new_*, reason, changed_by, at)

grade_items (course, title, max_points, kind)   grades (grade_item, student, points, by, at)
final_grades (course, student, value, control_form, date)   grade_scales (min_points → оценка)

certificate_types (code, title, template, auto_issue, fields_schema JSONB, sla_days)
requests (id uuid, student, type, payload JSONB, status, assigned_to, comment, document, verify_code)
   ─< request_events (from, to, by, at, comment)

notifications (user, kind, title, body, link, created_at, read_at)
notification_dispatch (user, entity, window) UNIQUE   — напоминание не уйдёт дважды
news (title, body_md, audience: all|faculty|course|group, audience_id, published_at, author)
audit_log (actor, action, entity, entity_id, before JSONB, after JSONB, ip, user_agent, at)
```

- **`AUTH_USER_MODEL` задаётся в первом же коммите.** Сменить модель пользователя после первой миграции в Django очень больно.
- **Занятия хранятся экземплярами по датам**, у объектов в URL — UUID. Штраф за опоздание считается функцией `final_score()` с параметризованными тестами.
- **Менеджеры с областью видимости**: `Request.objects.for_student(user)`, `Course.objects.for_teacher(user)`. Через них проходит любое чтение, поэтому студент физически не получает чужой queryset.

## 4. Слои и контракт между B и C

```
web/ (C)                              domain/ (B)
URL → view ──вызывает──► services / selectors ──► models
         │                        │
         └─► template + HTMX-фрагмент     возвращают frozen dataclass (DTO)
                                  └─ ошибки — наследники core.errors.AppError (A)
```

| Слой | Где | Кто | Правило |
|---|---|---|---|
| `models.py`, `managers.py` | `domain/<app>/` | B | Данные и менеджеры с областью видимости (`for_student`, `for_teacher`) |
| `services.py` (запись), `selectors.py` (чтение), `dto.py` | `domain/<app>/` | B | Принимают `user` первым аргументом и сами ограничивают выборку. Чужой объект — исключение `NotFound`. Возвращают `@dataclass(frozen=True)`, а не модели. |
| `forms.py` | `domain/<app>/` | B | Валидация бизнес-правил (дедлайн, политика, размер файла) |
| `views.py`, `urls.py` | `web/` | C | Тонкие: `@require_perm(...)` → вызов сервиса → шаблон. Для HTMX-запроса отдают фрагмент, для обычного — страницу целиком. |
| `templates/<раздел>/`, `templates/ui/` | `web/` | C | Страницы, фрагменты `_partials/`, компоненты дизайн-системы |

**Контракт — сигнатуры сервисов с DTO.** B пишет их в S0 с заглушками на данных сидера (задача #7). C сразу верстает по ним реальные экраны и не ждёт реализации.
A ревьюит каждый view на `@require_perm`, а тест-сторож не пропустит view без него.
Границу между модулями держит `tests/test_architecture.py`: тест падает, если `domain/` импортирует `web/` или `web/` импортирует `domain.*.models` / `domain.*.managers` в обход селекторов.

## 5. URL-карта (контур)

| Раздел | URL | Что внутри |
|---|---|---|
| вход | `/login/`, `/logout/`, `/password/` | Встроенные views Django со своими шаблонами |
| студент | `/` (Сегодня), `/schedule/?week=`, `/schedule.ics?token=` | Агрегат «Сегодня», неделя переключается фрагментом |
| учёба | `/courses/`, `/courses/<uuid>/`, `/courses/<uuid>/s/<uuid>/`, `/assignments/<uuid>/submit/` | Вкладки-разделы, форма сдачи (`hx-post`) |
| успеваемость | `/grades/`, `/grades/<uuid>/`, `/curriculum/` | |
| заявки | `/requests/`, `/requests/new/<type>/`, `/requests/<uuid>/`, `/requests/<uuid>/pdf/`, `/verify/<code>/` (публичный) | |
| уведомления | `/notifications/`, `/notifications/badge/` (HTMX-опрос раз в 60 с), `/news/` | |
| преподаватель | `/t/courses/`, `/t/courses/<uuid>/sections/`, `/t/assignments/<uuid>/`, `/t/submissions/<uuid>/grade/`, `/t/lessons/<uuid>/reschedule/`, `/t/gradebook/<uuid>/` | Конструктор, ДЗ и политики, проверка, перенос (конфликты + 3 слота) |
| админ | `/a/` (статистика), `/a/users/`, `/a/requests/`, `/a/audit/`, `/a/templates/` | Наши экраны для роли «Админ» |
| служебное | `/health/`, `/ready/`, `/metrics/` (только из внутренней сети), `/<секрет>/django-admin/` (только команда, staff) | |
| файлы | `/files/<uuid>/` | Проверка прав → `X-Accel-Redirect` → Caddy отдаёт файл |

Ошибки — свои шаблоны 403/404/500 без технических деталей. Для HTMX-запросов ошибка приходит фрагментом-тостом.

## 6. Структура репозитория

**Решение 04.11:** код разделён на четыре модуля — по одному на участника и модуль тестов. Каждый работает в своей папке, а контракт B ↔ C (сервисы и DTO) стал границей между модулями `domain/` и `web/`. Первая версия с общими папками `apps/<app>/` — в «Отвергнутых вариантах» п. 1.
Как запускать и где что лежит в деталях — [PROJECT.md](../../PROJECT.md) в корне репозитория.

| Модуль | Участник | Что внутри |
|---|---|---|
| `core/` | 1 — A | Настройки, `User` и роли, права, вход, аудит, экраны админа, служебные URL, общие ошибки |
| `domain/` | 2 — B | Модели, менеджеры, сервисы, селекторы, DTO, формы, задачи Celery, сидер |
| `web/` | 3 — C | Views и URL, шаблоны, HTMX-фрагменты, компоненты `ui/`, статика |
| `tests/` | все, каркас — A | `tests/<модуль>/` у владельца модуля; сторож границ, матрица прав, E2E и k6 — у A |

```
dekanat/
├─ CLAUDE.md                     # общий контекст для Claude: цель, стек, команды, правила, DoD
├─ PROJECT.md                    # устройство проекта: модули, команды, БД, Docker
├─ README.md                     # запуск, тестовые аккаунты, ссылка на прод
├─ pyproject.toml, uv.lock       # зависимости, команды `uv run poe …`, ruff, pytest
├─ manage.py, Dockerfile, .env.example, .pre-commit-config.yaml, .gitattributes (eol=lf)
├─ core/                         # ── участник 1 (A) ────────────────────────────────────────────
│  ├─ CLAUDE.md
│  ├─ settings/                  # base · dev · test · prod · components (БД и кэш из URL)
│  ├─ urls.py · celery.py · wsgi.py · errors.py (AppError → NotFound)
│  ├─ users/                     # кастомный User: UUID, роль, отчество
│  ├─ health/                    # /health/, /ready/
│  ├─ access/                    # роли → разрешения, require_perm (#13)
│  ├─ accounts/                  # вход, профиль, сессии (#12)
│  ├─ audit/                     # журнал аудита (#26)
│  └─ adminpanel/                # экраны роли «Админ», статистика, свои шаблоны (#25, #40)
├─ domain/                       # ── участник 2 (B) ────────────────────────────────────────────
│  ├─ CLAUDE.md                  # слои, сервисы и DTO, исключения, транзакции
│  ├─ org/ schedule/ courses/ assignments/ grades/ requests/ notifications/
│  │    └─ models.py managers.py services.py selectors.py dto.py forms.py tasks.py
│  ├─ requests/templates/certificates/   # шаблоны справок для PDF
│  └─ seed/                      # management-команда seed --profile demo|load (Faker ru_RU)
├─ web/                          # ── участник 3 (C) ────────────────────────────────────────────
│  ├─ CLAUDE.md                  # компоненты, 3 состояния, мобильность 360 px, a11y, тексты
│  ├─ views, urls.py
│  ├─ templates/                 # base.html, layouts/, ui/, <раздел>/ и <раздел>/_partials/
│  └─ static/                    # src/input.css (Tailwind), js/ (app.js, sw.js), vendor/ (htmx, alpine-csp, sortable, chart.js)
├─ tests/                        # ── модуль тестов ─────────────────────────────────────────────
│  ├─ CLAUDE.md · conftest.py · test_architecture.py (сторож границ модулей)   — A
│  ├─ core/ (A) · domain/ (B) · web/ (C)
│  ├─ authz/                     # матрица прав, сторож require_perm                              — A
│  ├─ e2e/                       # Playwright                                                    — A + C
│  └─ load/                      # k6-сценарии, REPORT.md                                        — A
├─ infra/                        # compose.yml, postgres/initdb/, caddy/, scripts/ (deploy, бэкапы) — A
├─ scripts/                      # setup.ps1, setup.sh, bootstrap.py — установка одной командой  — A
├─ docs/                         # plan/, tz/, plans/, adr/, prompts.md, screens/
├─ tracker/                      # Excel-трекеры и их генератор
├─ .claude/                      # settings.json (хуки), agents/, skills/                        — A
└─ .github/workflows/            # ci.yml, deploy.yml, security.yml, load.yml                    — A
```

**Направление зависимостей:** `web → domain → core`, и `web → core` (права, ошибки). `domain` не импортирует `web`, `web` не импортирует модели и менеджеры `domain`.

**БД для разработки:** один сервер PostgreSQL + Redis в Docker (`infra/compose.yml`, порт 5433), у каждого участника своя база `dekanat_a/b/c` и свой индекс Redis.
Тестовые базы `test_<имя>` поэтому тоже не пересекаются. Сейчас сервер стоит у A, потом переедет на VPS. Подключение к нему — через SSH-туннель, код и `.env` при этом не меняются.

## 7. Масштабирование

| Шаг | Когда | Что делаем |
|---|---|---|
| 0. Один VPS | до ~15 тыс. пользователей | Как в п. 2. Кэш расписания и фрагментов по группам: ~400 групп вместо 10 тыс. студентов. HTMX-фрагменты лёгкие. |
| 1. Вертикально | рост в 2 раза | VPS 8 vCPU / 16 ГБ, больше воркеров gunicorn, больше `shared_buffers`. |
| 2. Горизонтально | 30–50 тыс. | `web` без состояния (сессии в Redis/БД, файлы в `Storage`) → `--scale web=3` за Caddy. PgBouncer. Файлы → S3 настройкой `STORAGES`. |
| 3. Разнесённо | 50 тыс.+ | Управляемый PostgreSQL с репликой (роутер БД Django для чтения), отдельный Redis, несколько узлов за балансировщиком. При необходимости брокер → RabbitMQ одной настройкой. |

Отсутствие состояния в `web` проверяется сценарием k6 `scale_out`: прогон при `--scale web=2`, сессии не теряются.
