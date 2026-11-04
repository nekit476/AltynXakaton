from django.apps import AppConfig
from django.contrib.auth.signals import user_logged_in


class AccountsConfig(AppConfig):
    name = "core.accounts"
    label = "accounts"
    verbose_name = "Вход и сессии"

    def ready(self) -> None:
        from core.accounts.sessions import set_session_age

        user_logged_in.connect(set_session_age, dispatch_uid="accounts.session_age")
