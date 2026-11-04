"""Явный список публичных адресов — открыты без входа и без require_perm.

Каждое добавление сюда проходит ревью A: это прямой вход мимо проверки прав.
View публичного адреса обязан быть помечен `@login_not_required` — это проверяет сторож.
"""

PUBLIC_URL_NAMES: frozenset[str] = frozenset(
    {
        "health:health",
        "health:ready",
        "accounts:login",
    }
)

# Нужен только вход, без отдельного разрешения: эти действия доступны любой роли.
AUTHENTICATED_ONLY_URL_NAMES: frozenset[str] = frozenset(
    {
        "accounts:logout",
    }
)

# Django admin защищён своей проверкой is_staff и путём из DJANGO_ADMIN_PATH.
PROTECTED_BY_OWN_CHECKS: frozenset[str] = frozenset({"admin"})
