"""Обход карты URL и поиск view без проверки прав. Используется тестом-сторожем."""

from collections.abc import Iterable, Iterator

from django.urls import URLPattern, URLResolver

from core.access.public import (
    AUTHENTICATED_ONLY_URL_NAMES,
    PROTECTED_BY_OWN_CHECKS,
    PUBLIC_URL_NAMES,
)


def iter_named_patterns(
    patterns: Iterable[URLPattern | URLResolver], namespace: str = ""
) -> Iterator[tuple[str, str | None, URLPattern]]:
    """Рекурсивно отдаёт (пространство имён, полное имя URL или None, шаблон)."""
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            nested = ":".join(part for part in (namespace, pattern.namespace) if part)
            yield from iter_named_patterns(pattern.url_patterns, nested)
        else:
            name = f"{namespace}:{pattern.name}" if namespace and pattern.name else pattern.name
            yield namespace, name, pattern


def find_unguarded(patterns: Iterable[URLPattern | URLResolver]) -> list[str]:
    """Нарушения: URL без имени, view без require_perm, публичный view без login_not_required."""
    problems = []
    for namespace, name, pattern in iter_named_patterns(patterns):
        if namespace.split(":")[0] in PROTECTED_BY_OWN_CHECKS:
            continue
        callback = pattern.callback
        if name is None:
            problems.append(f"{pattern.pattern}: у URL нет имени — его не внести в матрицу прав")
        elif name in PUBLIC_URL_NAMES:
            if getattr(callback, "login_required", True):
                problems.append(f"{name}: публичный, но view без @login_not_required")
        elif name in AUTHENTICATED_ONLY_URL_NAMES:
            if not getattr(callback, "login_required", True):
                problems.append(f"{name}: нужен вход, а view помечен @login_not_required")
        elif not getattr(callback, "_required_perm", None):
            problems.append(f"{name}: нет @require_perm и нет в core/access/public.py")
    return problems


def all_url_names(patterns: Iterable[URLPattern | URLResolver]) -> set[str]:
    return {name for _, name, _ in iter_named_patterns(patterns) if name}
