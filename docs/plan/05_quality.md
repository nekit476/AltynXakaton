# 05. Тестирование и CI/CD

Весь код на Python, поэтому и тесты на Python, включая E2E. Один инструмент (pytest), один отчёт (Allure).

## 1. Пирамида тестов

| Уровень | Инструмент | Что проверяем | Кто пишет | Где бежит |
|---|---|---|---|---|
| Юнит (сервисы) | pytest + parametrize, **hypothesis**, Allure | Чистая логика: штраф за опоздание, окна напоминаний (72/24/3 ч), конфликты переноса и подбор свободных слотов, пороги оценок, «что нужно до зачёта», машина статусов заявки | B (+ A ревьюит) | Каждый PR |
| Интеграция (сервисы + БД) | **pytest-django** на реальном PostgreSQL (service-контейнер в CI), factory_boy | Сервисы и селекторы: транзакции, `on_commit`, менеджеры `for_student` / `for_teacher` | B, A | Каждый PR |
| Views и шаблоны | Django test client, `assertContains`, `assertTemplateUsed` | Страница и HTMX-фрагмент: нужный шаблон, ключевой текст, коды ошибок, сообщения формы, нет утечки чужих данных в HTML | C (+ A ревьюит права) | Каждый PR |
| **Права (authz)** | pytest, матрица из YAML по именам URL | Роль × URL × свой/чужой объект × (GET, POST, HTMX) → ожидаемый код. Тест-сторож «нет view без `require_perm`». Сценарий «студент 1 ↔ студент 2». | **A** | Каждый PR, **блокирует merge** |
| Задачи Celery | pytest + `CELERY_TASK_ALWAYS_EAGER` | Идемпотентность напоминаний, «автоноль», уведомления только после коммита (`django_capture_on_commit_callbacks`) | B | Каждый PR |
| Конфигурация | `manage.py check --deploy --fail-level WARNING`, `makemigrations --check --dry-run` | Безопасные настройки прода, нет забытых миграций | A | Каждый PR |
| Шаблоны | **djLint** (линт и форматирование), `grep` на `\|safe` / `mark_safe` / `raw(` | Чистые шаблоны, запрещённые конструкции | C, A | Каждый PR |
| E2E | **Playwright для Python** (`pytest-playwright`): проекты `desktop` и `mobile` (360×800, тач) | 5 сквозных сценариев из [01_product.md](01_product.md#5-пять-сквозных-сценариев-для-демо-и-e2e). Нет горизонтального скролла на 360 px. HTMX-обновления видны без перезагрузки. | A + C | После деплоя на staging |
| Доступность | `axe-playwright-python`, Lighthouse CI | Нет нарушений axe уровня serious/critical. Lighthouse mobile: Performance ≥ 90, Accessibility ≥ 95. | C | После деплоя на staging |
| Безопасность | gitleaks, pip-audit, Trivy, ruff `S`-правила (bandit), **OWASP ZAP** baseline + active scan | См. [03_security.md §10](03_security.md#10-чек-лист-перед-сдачей) | A | PR (статика), staging (ZAP) |
| **Нагрузка** | **k6** + Grafana | Раздел 2 | A | Вручную, перед заморозкой |
| Бэкап и восстановление | `restore.sh` в чистую БД + smoke | Бэкап реально восстанавливается | A | Руками перед сдачей |

Правила тестов из скилла «Разработка» действуют для всех:
- фикстуры вместо копипасты, параметризация вместо копий;
- `pytest.raises(..., match=...)`;
- `@allure.title` у каждого теста;
- проверяется не только код ответа, но и **почему**: тип исключения `AssignmentClosed`, сработавшая политика, текст ошибки в форме.

**Тестовые данные:**
- factory_boy для тестов;
- `manage.py seed --profile load` для нагрузки: 10 тыс. студентов, 400 групп, ~1 200 курсов, ~136 тыс. занятий, ~300 тыс. сдач, ~1 млн уведомлений.

## 2. Нагрузочное тестирование (k6)

Почему k6, а не Locust:
- тысячи виртуальных пользователей с одного ноутбука;
- пороги (`thresholds`) прямо в сценарии роняют прогон;
- у Locust Python-генератор упирается в GIL и сам становится узким местом.

Сценарии k6 — это небольшие JS-файлы в `load/`, исключение из правила «всё на Python», оправданное инструментом.

| Сценарий | Профиль | Что имитирует | Пороги |
|---|---|---|---|
| `smoke` | 1 VU, 1 мин | Скрипт работает, данные на месте | ошибок = 0 |
| `morning_rush` | 0 → 2 000 VU за 5 мин, 10 мин держим | Вход (часть VU с готовой сессией) → `/` → неделя расписания (фрагмент) → бейдж уведомлений | p95 < 300 мс, ошибок < 0,5 % |
| `grades_published` | 0 → 1 500 VU за 30 с | Всплеск `/grades/` после выкладки оценок | p95 < 500 мс |
| `deadline_rush` | 500 VU, файлы 2–10 МБ, 15 мин | Последний час перед дедлайном (проверяет и буферизацию Caddy) | p95 загрузки < 1 с, ошибок < 0,5 % |
| `certificates_burst` | 200 справок за 5 мин | Очередь PDF: страница отвечает сразу, воркер разгребает | p95 < 300 мс, очередь пуста за ≤ 3 мин |
| `stress` | +100 RPS каждые 2 мин до отказа | **Потолок** и подбор числа воркеров gunicorn | Отчётная цифра «сервер держит N RPS» |
| `soak` | 300 RPS, 1 час | Утечки памяти, рост соединений, разрастание Redis | RAM контейнеров не растёт > 10 % |
| `scale_out` | `morning_rush` при `--scale web=2` | Отсутствие состояния в `web`: сессии не теряются | Как `morning_rush` |

**Порядок работы:**
1. Прогон с отдельной машины, на VPS включён профиль `monitoring`.
2. После прогона ищем узкое место: CPU у `web`, медленные запросы в логе PostgreSQL, N+1 (django-debug-toolbar на staging-копии), argon2.
3. Чиним: `select_related` / `prefetch_related`, индекс, кэш фрагмента, число воркеров. Повторяем прогон.
4. Каждую итерацию «было → стало» с графиками Grafana записываем в `load/REPORT.md`.

**CSRF в k6:** сценарий сначала получает форму входа, вытаскивает `csrfmiddlewaretoken` и шлёт его с POST, как браузер. CSRF ради теста не отключаем.

## 3. Локальные проверки (pre-commit)

`ruff check --fix`, `ruff format`, `mypy` (django-stubs, строго на `apps/*/services.py`), `djlint --reformat`, `gitleaks protect --staged`.
Для Claude Code те же форматтеры висят на хуке после каждой правки файла (см. [06_team_roadmap.md](06_team_roadmap.md#5-работа-с-claude-code)).

## 4. CI/CD-пайплайн (GitHub Actions)

```
PR в main ─────────────────────────────────────────────────────────────────────────┐
  ├─ lint:     ruff check · ruff format --check · mypy · djlint --check           │ параллельно,
  │            · grep запрещённых конструкций (|safe, mark_safe, raw(, extra()     │ ~5–7 мин
  ├─ test:     pytest (unit + integration + views + authz + celery)                │
  │            с postgres/redis services · coverage ≥ 80 % на services/selectors   │
  │            · Allure-отчёт артефактом                                           │
  ├─ django:   check --deploy --fail-level WARNING · makemigrations --check        │
  │            · tailwind build + collectstatic (ломается — PR красный)            │
  └─ security: gitleaks · pip-audit · ruff S                                       ┘
  Правила ветки main: только через PR, всё зелёное, 1 аппрув человека, squash-merge.

merge в main ──► build: docker buildx (стадия tailwind → python) → ghcr.io/…/dekanat:<sha> → Trivy
             ──► deploy-staging: SSH → deploy.sh <sha> → /ready/
             ──► e2e-staging: pytest-playwright desktop + mobile · axe · Lighthouse CI
             ──► zap-staging: ZAP baseline · отчёт артефактом

тег v* (или workflow_dispatch) ──► deploy-prod: тот же <sha>, что прошёл staging → smoke
workflow_dispatch ──► load: k6 <сценарий> → отчёт артефактом
ночью (cron)      ──► ZAP active scan по staging · pip-audit (новые CVE)
```

- **Один образ для `web`, `worker` и `beat`**, и в прод едет ровно тот `<sha>`, который прошёл staging.
- **Allure-отчёт** публикуется артефактом или в GitHub Pages и пойдёт скриншотом в PDF.
- **Dependabot** — pip, docker, github-actions. JS-библиотеки в `static/vendor/` обновляем руками раз за проект с проверкой changelog.
- **Секреты CI:** `DEPLOY_SSH_KEY`, `DEPLOY_HOST` (GHCR — встроенный `GITHUB_TOKEN`). В логи не печатаются.

## 5. Definition of Done для задачи

1. Код соответствует ТЗ и плану этапа (`docs/tz`, `docs/plans`).
2. Тесты на требования есть, весь `pytest` зелёный, `ruff` и `djlint` — ноль замечаний.
3. Новый URL добавлен в матрицу прав (включая HTMX-вариант).
4. Экран проверен на 360 px и на ПК, есть пустое, загрузочное и ошибочное состояния.
5. PR ≤ ~400 строк, пройден агент `security-reviewer`, есть аппрув напарника.
6. Ключевой промпт записан в `docs/prompts.md`, скриншот — в `docs/screens/`.
