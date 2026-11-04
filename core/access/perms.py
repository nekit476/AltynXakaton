"""Перечень разрешений проекта.

Разрешение — действие, роль — набор разрешений (core/access/roles.py). Поэтому новая роль
(например, «сотрудник деканата») добавляется строкой в ROLE_PERMISSIONS, без правки views.

Новое разрешение: строка здесь → `uv run poe makemigrations` (Django создаст его в БД) →
выдать ролям в roles.py. Модель Capability хранит их все в одном приложении `access`.
"""

from enum import StrEnum


class Perm(StrEnum):
    """Полные имена разрешений в формате Django: `<app_label>.<codename>`."""

    # Всем, кто вошёл
    VIEW_DASHBOARD = "access.view_dashboard"
    # Студент
    VIEW_OWN_STUDY = "access.view_own_study"
    SUBMIT_ASSIGNMENTS = "access.submit_assignments"
    CREATE_REQUESTS = "access.create_requests"
    # Преподаватель
    MANAGE_OWN_COURSES = "access.manage_own_courses"
    GRADE_SUBMISSIONS = "access.grade_submissions"
    RESCHEDULE_OWN_LESSONS = "access.reschedule_own_lessons"
    # Администратор (и в будущем — сотрудник деканата)
    PROCESS_REQUESTS = "access.process_requests"
    MANAGE_USERS = "access.manage_users"
    VIEW_STATISTICS = "access.view_statistics"
    VIEW_AUDIT_LOG = "access.view_audit_log"

    @property
    def codename(self) -> str:
        return self.value.split(".", 1)[1]


DESCRIPTIONS: dict[Perm, str] = {
    Perm.VIEW_DASHBOARD: "Видеть «Сегодня», расписание, уведомления и свой профиль",
    Perm.VIEW_OWN_STUDY: "Видеть свои предметы, оценки и учебный план",
    Perm.SUBMIT_ASSIGNMENTS: "Сдавать задания",
    Perm.CREATE_REQUESTS: "Заказывать справки и подавать заявления, видеть свои заявки",
    Perm.MANAGE_OWN_COURSES: "Вести свои курсы: разделы, материалы, задания, дедлайны",
    Perm.GRADE_SUBMISSIONS: "Проверять сдачи и ставить оценки по своим курсам",
    Perm.RESCHEDULE_OWN_LESSONS: "Переносить и отменять свои занятия",
    Perm.PROCESS_REQUESTS: "Обрабатывать очередь заявок и справок",
    Perm.MANAGE_USERS: "Управлять пользователями, группами и ролями",
    Perm.VIEW_STATISTICS: "Видеть статистику",
    Perm.VIEW_AUDIT_LOG: "Видеть журнал аудита",
}
