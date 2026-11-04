"""Модель пользователя.

Своя модель задана с первой миграции: заменить AUTH_USER_MODEL после неё в Django
очень дорого (02_architecture.md §3). Профиль студента и преподавателя (группа,
факультет, кафедра) — отдельные модели участника B в domain/org со ссылкой на User.
"""

import uuid

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class Role(models.TextChoices):
    """Роль определяет, какой кабинет видит пользователь.

    Права проверяются не по роли, а по разрешениям её группы (задача #13): роль
    «сотрудник деканата» добавляется новой группой без переписывания кода.
    """

    STUDENT = "student", "Студент"
    TEACHER = "teacher", "Преподаватель"
    ADMIN = "admin", "Администратор"


class DekanatUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # Суперпользователь — командный аккаунт для Django admin. Без явной роли он
        # получил бы «студента» по умолчанию и не увидел бы экраны администратора.
        extra_fields.setdefault("role", Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    # UUID вместо счётчика: id попадает в URL, и людей нельзя перебрать по /users/1, /2, …
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patronymic = models.CharField("отчество", max_length=150, blank=True)
    # По умолчанию — роль с наименьшими правами: забытая роль не даёт лишнего доступа.
    role = models.CharField(
        "роль", max_length=16, choices=Role.choices, default=Role.STUDENT, db_index=True
    )

    objects = DekanatUserManager()

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"

    def __str__(self) -> str:
        return self.get_full_name() or self.username

    def get_full_name(self) -> str:
        # Русский порядок «Фамилия Имя Отчество»; AbstractUser склеивает «Имя Фамилия».
        parts = (self.last_name, self.first_name, self.patronymic)
        return " ".join(part for part in parts if part)
