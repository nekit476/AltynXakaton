"""Проверки живости и готовности.

/health/ — процесс жив (Docker healthcheck, Caddy). БД не трогает: если упадёт база,
контейнер web не должен перезапускаться по кругу.
/ready/ — приложение может обслуживать запросы: БД и кэш отвечают (deploy.sh, k6, мониторинг).

Оба адреса публичные: они нужны до входа в систему и вне её.
"""

import logging
import uuid
from collections.abc import Callable

from django.contrib.auth.decorators import login_not_required
from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

STATUS_OK = "ok"
STATUS_FAIL = "fail"
HTTP_SERVICE_UNAVAILABLE = 503
CACHE_PROBE_TIMEOUT_S = 5


class CheckFailedError(Exception):
    """Проверка дошла до конца, но результат неверный."""


def check_database() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def check_cache() -> None:
    # Уникальный ключ: параллельные проверки из разных потоков не мешают друг другу.
    key = f"health:{uuid.uuid4().hex}"
    cache.set(key, STATUS_OK, timeout=CACHE_PROBE_TIMEOUT_S)
    try:
        if cache.get(key) != STATUS_OK:
            raise CheckFailedError("кэш не вернул записанное значение")
    finally:
        cache.delete(key)


READINESS_CHECKS: dict[str, Callable[[], None]] = {
    "database": check_database,
    "cache": check_cache,
}


def run_check(name: str, check: Callable[[], None]) -> str:
    """Запускает проверку; любую ошибку переводит в "fail" и пишет в лог."""
    try:
        check()
    except Exception:
        # Ловим Exception, а не BaseException: KeyboardInterrupt и SystemExit проходят насквозь.
        # Подробности — только в лог: ответ публичный, хосты и тексты ошибок наружу не отдаём.
        logger.exception("Проверка готовности %s не прошла", name)
        return STATUS_FAIL
    return STATUS_OK


@login_not_required
@never_cache
@require_GET
def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": STATUS_OK})


@login_not_required
@never_cache
@require_GET
def ready(request: HttpRequest) -> JsonResponse:
    checks = {name: run_check(name, check) for name, check in READINESS_CHECKS.items()}
    is_ready = all(status == STATUS_OK for status in checks.values())
    return JsonResponse(
        {"status": STATUS_OK if is_ready else STATUS_FAIL, "checks": checks},
        status=200 if is_ready else HTTP_SERVICE_UNAVAILABLE,
    )
