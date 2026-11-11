# syntax=docker/dockerfile:1
# Один образ для web, worker и beat — разная только команда запуска (02_architecture.md §2).
# Стадия сборки Tailwind (standalone CLI, без Node) добавится в задаче #19.

FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=core.settings.prod

# Та же версия uv, что у разработчиков: одинаково читает uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /bin/

WORKDIR /app

# Зависимости — отдельным слоем: правка кода не пересобирает окружение.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .

# collectstatic импортирует настройки, а им нужны переменные. Значения фиктивные
# и живут только в этом слое: к БД при сборке никто не подключается.
RUN DJANGO_SECRET_KEY=build-only \
    DJANGO_ALLOWED_HOSTS=build \
    DATABASE_URL=postgres://build:build@localhost:5432/build \
    python manage.py collectstatic --noinput

# Не от root (03_security.md §8). Писать можно только в каталог файлов.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/var/files \
    && chown -R app:app /app/var
USER app

EXPOSE 8000
# Параметры gunicorn — в переменной: прод переопределяет её целиком (6 процессов × 4 потока,
# 04_infra.md §5), а команда запуска остаётся одна. max-requests — страховка от утечек памяти.
ENV GUNICORN_CMD_ARGS="--bind 0.0.0.0:8000 --worker-class gthread --workers 2 --threads 4 --timeout 30 --max-requests 5000 --max-requests-jitter 500 --access-logfile -"
CMD ["gunicorn", "core.wsgi:application"]
