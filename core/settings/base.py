"""Общие настройки для всех окружений.

Всё, что отличается между машинами (БД, Redis, секреты, хосты), приходит из переменных
окружения: при разработке — из файла .env в корне, в Docker и на сервере — снаружи.
"""

from datetime import timedelta
from pathlib import Path

import environ

from core.settings.components import cache_settings, database_settings

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env()
# .env есть только у разработчика; в Docker и CI переменные задаются снаружи,
# и уже заданные переменные окружения .env не перекрывает.
if (BASE_DIR / ".env").is_file():
    environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
# Путь к Django admin не /admin/: его знает только команда (03_security.md §8).
DJANGO_ADMIN_PATH = env.str("DJANGO_ADMIN_PATH", default="team-admin/")

# ---------------------------------------------------------------- приложения по модулям
# Участник 1 (A) — платформа: пользователи, права, вход, служебные URL.
CORE_APPS = [
    "core.users",
    "core.access",
    "core.accounts",
    "core.health",
]
# Участник 2 (B) — учебная логика: модели, сервисы, селекторы, задачи.
DOMAIN_APPS = [
    "domain.org",
    "domain.schedule",
    "domain.courses",
    "domain.assignments",
    "domain.grades",
    "domain.requests",
    "domain.notifications",
    "domain.seed",
]
# Участник 3 (C) — интерфейс: views, шаблоны, статика.
WEB_APPS = [
    "web",
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "axes",
    *CORE_APPS,
    *DOMAIN_APPS,
    *WEB_APPS,
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Сразу после SecurityMiddleware: статика отдаётся до сессий и авторизации.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # request.htmx: view отдаёт фрагмент на HTMX-запрос и страницу целиком на обычный.
    "django_htmx.middleware.HtmxMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Вход обязателен по умолчанию (03_security.md §2, A01): публичный адрес помечается
    # @login_not_required и вносится в core/access/public.py.
    "core.access.middleware.DekanatLoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Последним: считает неудачные входы и блокирует перебор (документация django-axes).
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "core.urls"
WSGI_APPLICATION = "core.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        # Шаблоны живут в своих модулях: web/templates/, позже core/adminpanel/templates/ и т.д.
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------- данные
DATABASES = {"default": database_settings(env.str("DATABASE_URL"))}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Задаётся до первой миграции: сменить модель пользователя потом очень дорого.
AUTH_USER_MODEL = "users.User"

REDIS_URL = env.str("REDIS_URL", default="")
CACHES = cache_settings(REDIS_URL)
# Сессии в БД с кэшем: скорость Redis, и сессии переживают его перезапуск (03_security.md §3).
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# ---------------------------------------------------------------- Celery
# Без Redis брокера нет: задачи выполняются сразу в том же процессе, воркер не нужен.
CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_TASK_ALWAYS_EAGER = not REDIS_URL
CELERY_TASK_EAGER_PROPAGATES = True
# Результаты задач никто не читает: уведомления и PDF пишут итог в БД сами.
CELERY_TASK_IGNORE_RESULT = True
CELERY_TIMEZONE = "Europe/Moscow"
# Расписание периодических задач (напоминания о дедлайнах) заполняет участник B.
CELERY_BEAT_SCHEDULE: dict = {}

# ---------------------------------------------------------------- вход
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "web:home"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTHENTICATION_BACKENDS = [
    # axes первым: заблокированный по перебору логин не дойдёт до проверки пароля.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
# Блокировка по логину, а не по IP: в вузовском Wi-Fi все сидят за одним NAT (03_security.md §3).
AXES_LOCKOUT_PARAMETERS = ["username"]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_RESET_ON_SUCCESS = True
# axes.W006 советует добавить IP. Не добавляем намеренно: из-за общего NAT вуза блокировка
# по IP закрыла бы вход всем студентам сразу. Мягкий лимит по IP — в Caddy (#27).
SILENCED_SYSTEM_CHECKS = ["axes.W006"]

PASSWORD_HASHERS = [
    "core.accounts.hashers.DekanatArgon2PasswordHasher",
    # Остальные — только чтобы проверить старые хеши; при входе они пересчитываются в argon2id.
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# Пароль демо-аккаунтов (manage.py demo_users). Только для разработки и staging.
DEMO_PASSWORD = env.str("DEMO_PASSWORD", default="")

# ---------------------------------------------------------------- пароли
# Подход NIST: длина и запрет известных паролей вместо «заглавная + цифра» (03_security.md §3).
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------- язык и время
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------- статика и файлы
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Файлы ДЗ и справок — вне статики и вне веб-корня, отдаются только после проверки прав.
MEDIA_ROOT = env.path("DJANGO_FILES_ROOT", default=BASE_DIR / "var" / "files")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# ---------------------------------------------------------------- логи
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
