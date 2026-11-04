from django.db import models

from core.access.perms import DESCRIPTIONS, Perm


class Capability(models.Model):
    """Носитель разрешений проекта. Таблицы у модели нет.

    Разрешения в Django привязаны к модели, а наши разрешения — к действиям, а не к таблицам.
    Неуправляемая модель без полей держит их все в одном месте (`access.<codename>`),
    и Django сам создаёт их в БД после миграций.
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = tuple((perm.codename, DESCRIPTIONS[perm]) for perm in Perm)

    def __str__(self) -> str:
        return "разрешения проекта"
