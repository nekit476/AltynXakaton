"""Декоратор require_perm — обязательная отметка прав на каждом view.

Тест-сторож tests/authz/test_guard.py падает на любом URL, у view которого нет отметки
`_required_perm` и которого нет в core/access/public.py: забытая проверка прав не пройдёт CI.
"""

import logging
from collections.abc import Callable
from functools import wraps

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import HttpRequest, HttpResponse

from core.access.perms import Perm

logger = logging.getLogger(__name__)

View = Callable[..., HttpResponse]


def has_perms(user, perms: tuple[str, ...]) -> bool:
    """Проверка прав, которая при любой ошибке отказывает (03_security.md §2, A10)."""
    try:
        return bool(user.is_authenticated and user.is_active and user.has_perms(perms))
    except Exception:
        # Exception, а не BaseException: KeyboardInterrupt проходит насквозь.
        logger.exception("Проверка прав %s упала — доступ запрещён", perms)
        return False


def require_perm(*perms: Perm | str) -> Callable[[View], View]:
    """Пускает во view только пользователя со всеми перечисленными разрешениями.

    Не вошёл — отправляем на вход (LoginRequiredMiddleware обычно делает это раньше).
    Вошёл, но прав нет — 403. Чужой объект — забота селектора: NotFound → 404.
    """
    if not perms:
        raise ImproperlyConfigured("require_perm без разрешений: укажи хотя бы одно из Perm")
    required = tuple(str(perm) for perm in perms)

    def decorator(view: View) -> View:
        @wraps(view)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            if has_perms(request.user, required):
                return view(request, *args, **kwargs)
            if not request.user.is_authenticated:
                # Импорт здесь: core.access грузится до готовности приложений, а модуль
                # auth.views тянет модели.
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())
            raise PermissionDenied

        wrapper._required_perm = required
        return wrapper

    return decorator
