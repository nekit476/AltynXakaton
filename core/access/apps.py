from django.apps import AppConfig
from django.db.models.signals import post_migrate, post_save


class AccessConfig(AppConfig):
    name = "core.access"
    label = "access"
    verbose_name = "Права доступа"

    def ready(self) -> None:
        from core.users.models import User

        post_migrate.connect(_sync_groups_after_migrate, sender=self)
        post_save.connect(_sync_user_group_on_save, sender=User, dispatch_uid="access.user_group")


def _sync_groups_after_migrate(sender, **kwargs) -> None:
    from core.access.roles import sync_role_groups

    sync_role_groups()


def _sync_user_group_on_save(sender, instance, raw=False, **kwargs) -> None:
    # raw — загрузка фикстур: связей ещё может не быть, группы выставит следующий save.
    if raw:
        return
    from core.access.roles import sync_user_group

    sync_user_group(instance)
