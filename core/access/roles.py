"""Роли как наборы разрешений и синхронизация групп Django.

Группа на роль (`student`, `teacher`, `admin`) с ровно теми разрешениями, что указаны здесь.
Группы пересобираются после каждого `migrate`, а пользователь попадает в группу своей роли
при сохранении, — поэтому права всегда соответствуют коду, а не ручным правкам в админке.
"""

from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Group, Permission

from core.access.perms import Perm
from core.users.models import Role, User

_EVERYONE = frozenset({Perm.VIEW_DASHBOARD})

ROLE_PERMISSIONS: dict[Role, frozenset[Perm]] = {
    Role.STUDENT: _EVERYONE | {Perm.VIEW_OWN_STUDY, Perm.SUBMIT_ASSIGNMENTS, Perm.CREATE_REQUESTS},
    Role.TEACHER: _EVERYONE
    | {Perm.MANAGE_OWN_COURSES, Perm.GRADE_SUBMISSIONS, Perm.RESCHEDULE_OWN_LESSONS},
    Role.ADMIN: _EVERYONE
    | {Perm.PROCESS_REQUESTS, Perm.MANAGE_USERS, Perm.VIEW_STATISTICS, Perm.VIEW_AUDIT_LOG},
}


def sync_role_groups() -> None:
    """Приводит группы ролей к ROLE_PERMISSIONS. Идемпотентна: повторный вызов ничего не меняет."""
    # Разрешения access создаёт обработчик auth в том же post_migrate; вызываем явно, чтобы
    # не зависеть от порядка обработчиков.
    create_permissions(apps.get_app_config("access"), verbosity=0)
    by_codename = {
        permission.codename: permission
        for permission in Permission.objects.filter(content_type__app_label="access")
    }
    for role, perms in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=role.value)
        group.permissions.set([by_codename[perm.codename] for perm in perms])


def sync_user_group(user: User) -> None:
    """Оставляет пользователя ровно в одной группе ролей — группе его роли."""
    wanted, _ = Group.objects.get_or_create(name=user.role)
    stale = user.groups.filter(name__in=Role.values).exclude(pk=wanted.pk)
    user.groups.remove(*stale)
    user.groups.add(wanted)
