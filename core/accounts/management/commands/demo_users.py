"""Демо-аккаунты для разработки: два студента, преподаватель, администратор.

Нужны сразу, чтобы входить и верстать экраны под каждой ролью, не дожидаясь сидера
(задачи B #16 и #66 — полноценные данные с группами, курсами и оценками).
Пароль у всех один: DEMO_PASSWORD из .env или значение по умолчанию. Данные вымышленные.
"""

from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.users.models import Role, User

# Вымышленный пароль демо-аккаунтов, только для разработки; на проде команда не запускается.
DEFAULT_DEMO_PASSWORD = "zachetka-demo-2026"  # noqa: S105


@dataclass(frozen=True)
class DemoUser:
    username: str
    last_name: str
    first_name: str
    patronymic: str
    role: Role


DEMO_USERS = (
    DemoUser("student", "Студентов", "Иван", "Петрович", Role.STUDENT),
    DemoUser("student2", "Должникова", "Анна", "Сергеевна", Role.STUDENT),
    DemoUser("teacher", "Преподавателев", "Пётр", "Ильич", Role.TEACHER),
    DemoUser("admin", "Админова", "Мария", "Олеговна", Role.ADMIN),
)


class Command(BaseCommand):
    help = "Создаёт или обновляет демо-аккаунты (student, student2, teacher, admin)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="разрешить запуск при DEBUG=False (только для staging)",
        )

    def handle(self, *args, force: bool = False, **options):
        # Известный пароль на проде — готовая дыра. На staging запускать осознанно, с --force.
        if not settings.DEBUG and not force:
            raise CommandError("DEBUG выключен: демо-аккаунты с известным паролем не создаю")
        password = getattr(settings, "DEMO_PASSWORD", "") or DEFAULT_DEMO_PASSWORD
        for demo in DEMO_USERS:
            user, created = User.objects.update_or_create(
                username=demo.username,
                defaults={
                    "last_name": demo.last_name,
                    "first_name": demo.first_name,
                    "patronymic": demo.patronymic,
                    "role": demo.role,
                    "is_active": True,
                },
            )
            user.set_password(password)
            user.save(update_fields=["password"])
            action = "создан" if created else "обновлён"
            self.stdout.write(f"{demo.username:<9} {demo.role.label:<14} {action}")
        self.stdout.write(self.style.SUCCESS(f"Пароль у всех: {password}"))
