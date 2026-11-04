"""Команда demo_users: демо-аккаунты для разработки."""

import allure
import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings

from core.accounts.management.commands.demo_users import DEFAULT_DEMO_PASSWORD, DEMO_USERS
from core.users.models import User


@pytest.mark.django_db
@allure.feature("Вход")
@allure.story("Демо-аккаунты")
class TestDemoUsers:
    """Демо-аккаунты всех ролей.

    Тесты:
      1. Создаются аккаунты всех ролей с рабочим паролем, повторный запуск не плодит дубли
      2. При DEBUG=False без --force команда отказывается работать
    """

    @override_settings(DEBUG=True, DEMO_PASSWORD="")
    @allure.title("Демо-аккаунты создаются с ролями и паролем, повтор не плодит дубли")
    def test_creates_accounts(self):
        call_command("demo_users")
        call_command("demo_users")

        users = {user.username: user for user in User.objects.all()}
        assert set(users) == {demo.username for demo in DEMO_USERS}
        for demo in DEMO_USERS:
            assert users[demo.username].role == demo.role
            assert users[demo.username].check_password(DEFAULT_DEMO_PASSWORD)

    @override_settings(DEBUG=False)
    @allure.title("Без DEBUG и --force команда отказывается")
    def test_refuses_without_debug(self):
        with pytest.raises(CommandError, match="DEBUG выключен"):
            call_command("demo_users")

        assert not User.objects.exists()
