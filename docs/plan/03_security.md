# 03. Безопасность: отдельный ресёрч

Опорные источники:
- [OWASP Top 10:2025](https://owasp.org/Top10/2025/) — финальная версия вышла в январе 2026;
- OWASP ASVS 5.0 (цель — уровень 2);
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/): Password Storage, Session Management, File Upload, Authorization, Django Security;
- NIST SP 800-63B (правила паролей);
- [документация Django по безопасности](https://docs.djangoproject.com/en/5.2/topics/security/) и чек-лист развёртывания.

Требования конкурса, которые проверит жюри:
1. Студент не открывает чужой профиль или заявку, даже подставив адрес.
2. Пароли не хранятся в открытом виде.
3. Ключи не лежат в коде и в браузере.
4. Данные только вымышленные.

Монолит на Django упрощает защиту. Нет отдельного API с токенами и нет CORS: сессия в HttpOnly-cookie и CSRF работают так, как задумано фреймворком.

## 1. Модель угроз (кратко)

| Кто | Чего хочет | Как может попробовать |
|---|---|---|
| Любопытный студент | Чужие оценки, заявки, ДЗ | Подмена UUID в URL, прямые запросы к страницам и фрагментам преподавателя |
| Студент-«хакер» | Поставить себе оценку, сдвинуть дедлайн | POST в `/t/submissions/<id>/grade/`, лишние поля в форме (`score=100`) |
| Внешний атакующий | Захват аккаунтов, утечка БД | Перебор паролей, XSS ради действий от имени жертвы, SQLi, вредоносный файл в ДЗ, SSRF через генерацию PDF |
| Бот | Положить сервис | Флуд входа, гигантские файлы, медленные загрузки (slowloris) |
| Неосторожный разработчик (или ИИ-ассистент) | — | Ключ в коммите, view без проверки прав, `DEBUG=True` в проде, `{{ x\|safe }}`, открытый порт БД |

Главный риск — **view или фрагмент без проверки прав, написанный ИИ**. Особенно HTMX-фрагменты: их легко забыть, потому что «их же вызывает только страница».
Основная защита — автоматика: безопасный режим по умолчанию (`LoginRequiredMiddleware`), тест-сторож, матрица прав и агент `security-reviewer` на каждый PR.

## 2. OWASP Top 10:2025 → наши меры

| # | Категория | Как закрываем |
|---|---|---|
| A01 | Broken Access Control | **`LoginRequiredMiddleware`** (Django 5.1+): любая страница по умолчанию требует входа, публичные помечаются `@login_not_required`. На каждом view **`@require_perm(...)`**. Чтение только через менеджеры с областью видимости (`for_student`, `for_teacher`), на чужой объект — **404, а не 403**. Тест-сторож и матрица прав (п. 4). Формы с явным `fields = [...]`, никогда `__all__`, поэтому лишнее поле `score` в POST игнорируется. |
| A02 | Security Misconfiguration | `DEBUG=False`. **`manage.py check --deploy --fail-level WARNING` в CI.** Свои страницы 403/404/500 без деталей. `ALLOWED_HOSTS` только наш домен. Django admin на секретном пути и только для staff-аккаунтов команды. Порты БД и Redis наружу не открыты. Контейнеры не от root. |
| A03 | Software Supply Chain Failures | `uv.lock` с хешами. JS-библиотеки (htmx, alpine-csp, sortable, chart.js) лежат в `web/static/vendor/` с зафиксированными версиями, без CDN. Образы с фиксированными версиями. `pip-audit` и Trivy в CI, Dependabot. Лицензии только MIT/BSD/Apache/OFL. |
| A04 | Cryptographic Failures | Только HTTPS (Caddy + HSTS). argon2id. `SECRET_KEY` и пароли только в `.env` на сервере (права 600) и в GitHub Secrets. `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`. |
| A05 | Injection | ORM с параметрами. `raw()` и `extra()` запрещены правилом в `CLAUDE.md` и проверкой в ревью. Автоэкранирование шаблонов. **`\|safe` и `mark_safe` запрещены**, кроме одного фильтра `markdown`: он прогоняет текст преподавателя через `nh3`. Имена файлов не попадают в пути. |
| A06 | Insecure Design | Бизнес-правила в сервисах на сервере: нельзя сдать после закрытия по политике, перенести чужую пару, поставить балл выше максимума. Лимиты на вход и загрузки. Подтверждение опасных действий. |
| A07 | Authentication Failures | **django-axes** (блокировка по логину), одинаковое сообщение «неверный логин или пароль», новая сессия при входе (Django делает `cycle_key` сам), «выйти везде», валидаторы паролей Django. Опционально TOTP для админа (django-otp). |
| A08 | Software or Data Integrity Failures | Деплой только из CI образом, который прошёл staging. Схема меняется только миграциями Django, а `makemigrations --check` в CI ловит забытые. `sha256` у файлов сдач. QR справки ведёт на `/verify/`, где код сверяется с БД. |
| A09 | Logging & Alerting Failures | JSON-логи с `request_id`, без паролей, cookie и тел запросов. `audit_log` на чувствительные действия (вход, роли, оценки, переносы, дедлайны, статусы заявок, действия админа). Сигналы `user_login_failed` и axes попадают в аудит. Алерт Grafana на всплеск 403/404/5xx. |
| A10 | Mishandling of Exceptional Conditions | `require_perm` при любой ошибке запрещает доступ. Таймауты на БД, Redis и PDF. `ATOMIC_REQUESTS` или явные `transaction.atomic`. Задачи Celery только через `on_commit` и идемпотентны (таблица `notification_dispatch` с уникальным ключом). |

## 3. Вход и сессии

| Параметр | Значение | Почему |
|---|---|---|
| Хеш пароля | **argon2id**, m = 19 МиБ, t = 2, p = 1 — свой подкласс `Argon2PasswordHasher` первым в `PASSWORD_HASHERS` | **У Django по умолчанию m = 100 МиБ и p = 8.** Это 100 МБ RAM на каждый вход. Наши параметры — минимум OWASP. |
| Сколько хешей одновременно | Не больше числа потоков gunicorn: 6 × 4 = 24 × 19 МиБ ≈ 460 МБ в пике | Отдельный семафор не нужен: потолок задаёт число потоков. Учтено в лимите памяти `web`. |
| Политика паролей | `MinimumLengthValidator(12)`, `CommonPasswordValidator` (встроенный список ~20 тыс.), `UserAttributeSimilarityValidator`, `NumericPasswordValidator` | Подход NIST: длина и запрет известных паролей вместо правил «заглавная + цифра». |
| Хранилище сессий | `SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"` | Скорость Redis, а сессии переживают его перезапуск. Отозвать сессию можно мгновенно. |
| Cookie | `SESSION_COOKIE_NAME = "__Host-sessionid"`; Secure, HttpOnly, SameSite=Lax, Path=/ | JS не видит cookie, она не уходит на поддомены. |
| CSRF | `CsrfViewMiddleware`. Для HTMX — `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'` на `<body>`. `CSRF_TRUSTED_ORIGINS` только наш домен. | Каждый POST от HTMX несёт токен, ничего не надо отключать. |
| Время жизни | При входе `request.session.set_expiry(...)`: студент — 14 дней, преподаватель — 7 дней, админ — 8 часов | Удобство студента против риска админа. |
| Лимиты входа | django-axes: `AXES_LOCKOUT_PARAMETERS = ["username"]`, 5 неудач → блокировка на 15 мин. Мягкий лимит по IP в Caddy. | **Вуз сидит за одним NAT**: блокировка по IP заблокировала бы всех. |
| Смена пароля | `update_session_auth_hash` для текущей сессии, остальные отзываются | Стандарт. |

## 4. Авторизация: как устроено и как проверяем

```python
# Без require_perm view не пройдёт тест-сторож. Вход проверяет LoginRequiredMiddleware.
@require_perm(Perm.REQUESTS_READ_OWN)
def request_detail(request, request_id: UUID):
    # Селектор ищет только среди заявок request.user: чужая → NotFound → 404.
    dto = selectors.get_own_request(request.user, request_id)
    template = "requests/_partials/detail.html" if request.htmx else "requests/detail.html"
    return render(request, template, {"req": dto})
```

- **Роли → разрешения.** Группы Django `student`, `teacher`, `admin` (и опционально `dean_office`) с наборами разрешений. Они создаются data-миграцией, а не руками.
- **Тест-сторож:** рекурсивно обходит `get_resolver().url_patterns` и падает, если у view нет атрибута `_required_perm` (его ставит декоратор) и view нет в явном списке `PUBLIC_VIEWS` (`login`, `verify`, `health`, `ready`).
- **Матрица прав:** один YAML. Для каждого имени URL записан ожидаемый код для `anon / student_own / student_foreign / teacher_own_course / teacher_foreign_course / admin`. Параметризованный pytest проверяет обычный GET, POST и HTMX-запрос (`HX-Request: true`), чтобы не пропустить фрагменты. Матрица же служит документацией прав для PDF.
- **Сценарий жюри:** у двух студентов есть заявка и сдача. Каждый ходит по UUID второго ко всем URL, ответ везде 404.
- **hypothesis** гоняет сервисы случайными данными (баллы, даты, политики) и ищет исключения вместо понятных ошибок. **ZAP active scan** по staging пробует формы.

## 5. Заголовки и транспорт

Django `SecurityMiddleware` + django-csp, HSTS ставит Caddy:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
                         img-src 'self' data:; connect-src 'self'; font-src 'self';
                         frame-ancestors 'none'; base-uri 'self'; form-action 'self'
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
X-Robots-Tag: noindex, nofollow
```

- **HTMX под строгий CSP:** `htmx.config.allowEval = false`, атрибуты `hx-on` не используем.
- **Alpine — только CSP-сборка** (`@alpinejs/csp`): обычная сборка вычисляет выражения через `new Function` и требует `unsafe-eval`.
- Inline-скриптов нет вообще. Конфигурация лежит в `web/static/js/app.js`.
- `style-src 'unsafe-inline'` — осознанная уступка: HTMX вставляет стиль индикатора загрузки. Скрипты при этом только свои.
- Проверка на проде через Mozilla Observatory или securityheaders.com, цель — A и выше. Скриншот пойдёт в PDF.

## 6. Файлы (ДЗ и материалы)

1. Caddy: `request_body max_size 25MB` и **буферизация тела** перед передачей в Django. Медленная загрузка с телефона не держит воркер.
2. Django: `DATA_UPLOAD_MAX_MEMORY_SIZE`, `FILE_UPLOAD_MAX_MEMORY_SIZE`. Валидатор формы проверяет `max_file_mb` и белый список расширений задания, а также **сигнатуру** файла (`filetype`), не только расширение.
3. Хранение вне статики в томе `files/` под UUID-именем, оригинальное имя только в БД.
4. Отдача: `/files/<uuid>/` → проверка прав → заголовок `X-Accel-Redirect` → Caddy (`intercept` + `file_server` по внутреннему пути) отдаёт файл с `Content-Disposition: attachment` и `nosniff`. Django не держит воркер на время скачивания.
5. Архивы не распаковываются на сервере.
6. ClamAV — опция (+1–1,5 ГБ RAM), запас под него есть.

## 7. Генерация PDF (справки)

- Шаблоны справок с автоэкранированием Django.
- У WeasyPrint **свой `url_fetcher`**: разрешены только локальные шрифты и картинки. Иначе поле «куда предоставляется» с `<img src="http://169.254.169.254/...">` превращается в SSRF.
- Генерация в воркере Celery с таймаутом.
- `/verify/<код>/` показывает минимум: тип, дату, «действительна» и ФИО в маске «Иванов И. И.».
- Водяной знак «КОНЦЕПТ — НЕ ЯВЛЯЕТСЯ ДОКУМЕНТОМ».

## 8. Сервер и контейнеры

| Мера | Как |
|---|---|
| SSH | Только ключи, `PermitRootLogin no`, `PasswordAuthentication no`, пользователь `deploy` |
| Фаервол | `ufw`: 22, 80, 443. `fail2ban` на SSH. |
| Обновления | `unattended-upgrades` |
| Docker | БД и Redis без `ports:`. `user:` непривилегированный, `cap_drop: [ALL]`, `no-new-privileges`, лимиты памяти на каждый сервис |
| БД | Пользователь приложения без superuser. Пароль на Redis. |
| Django admin | Путь из переменной окружения (не `/admin/`), доступ только `is_staff` командным аккаунтам, вход тоже через axes |
| Секреты | `.env` только на сервере, в репозитории `.env.example`. Хук Claude запрещает читать и писать `.env*`. `gitleaks` в pre-commit и CI. |
| Бэкапы | `pg_dump` каждую ночь, хранение 7 дней, копия вне VPS. **Восстановление проверяем руками.** |
| ИИ-ключи (если будет помощник) | Только в `.env` на сервере. Вызов идёт из Celery-задачи или view, в браузер ключ не уходит. Помощник не меняет данные, отвечает по FAQ, текст пользователя не исполняется как инструкция. |

## 9. Данные и юридическое

- Только вымышленные данные: `manage.py seed`, Faker `ru_RU`, вымышленные номера зачёток.
- При импорте открытого расписания **ФИО преподавателей заменяются**.
- Плашка «Концепт для конкурса, не официальный сервис», свой логотип.
- Архитектура построена так, будто это реальные ПДн (152-ФЗ): минимум полей, маскирование в логах, аудит доступа.

## 10. Чек-лист перед сдачей

- [ ] Тест-сторож и матрица прав зелёные, включая HTMX-фрагменты
- [ ] Сценарий «студент 1 ↔ студент 2» — везде 404
- [ ] `manage.py check --deploy --fail-level WARNING` без замечаний
- [ ] В шаблонах нет `|safe` и `mark_safe` (кроме фильтра `markdown`), в коде нет `raw()` и `extra()` — проверка `grep` в CI
- [ ] ZAP baseline и active scan без High/Medium
- [ ] `pip-audit` и Trivy без High/Critical (или с обоснованием)
- [ ] `gitleaks detect` по всей истории — чисто
- [ ] Observatory / securityheaders: A и выше, CSP без `unsafe-eval`
- [ ] В БД пароли вида `argon2$argon2id$v=19$m=19456,t=2,p=1$...` — скриншот для PDF
- [ ] `nmap` по IP: открыты только 22, 80, 443. Django admin не на `/admin/`.
- [ ] Бэкап снят и восстановлен на чистую БД
- [ ] В `web/static/` и шаблонах нет ключей (`grep`)
