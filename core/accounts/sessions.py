"""Срок жизни сессии по роли (03_security.md §3): удобство студента против риска админа."""

from datetime import timedelta

from core.users.models import Role

SESSION_AGE_BY_ROLE: dict[str, timedelta] = {
    Role.STUDENT: timedelta(days=14),
    Role.TEACHER: timedelta(days=7),
    Role.ADMIN: timedelta(hours=8),
}
# Роль, которой нет в таблице, получает самый короткий срок: лишний вход лучше лишнего доступа.
FALLBACK_SESSION_AGE = min(SESSION_AGE_BY_ROLE.values())


def set_session_age(sender, request, user, **kwargs) -> None:
    """Обработчик user_logged_in: выставляет срок сессии по роли вошедшего."""
    age = SESSION_AGE_BY_ROLE.get(user.role, FALLBACK_SESSION_AGE)
    request.session.set_expiry(int(age.total_seconds()))
