"""Роли → разрешения → группы и декоратор require_perm (core/access)."""

import logging

import allure
import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory

from core.access import Perm, require_perm
from core.access.roles import ROLE_PERMISSIONS, sync_role_groups
from core.users.models import Role

ROLE_CASES = [pytest.param(role, id=role.value) for role in ROLE_PERMISSIONS]


def group_codenames(role: Role) -> set[str]:
    return set(Group.objects.get(name=role).permissions.values_list("codename", flat=True))


@pytest.fixture
def protected_view():
    @require_perm(Perm.CREATE_REQUESTS)
    def view(request):
        return HttpResponse("ok")

    return view


@pytest.fixture
def make_request(rf: RequestFactory):
    def factory(user):
        request = rf.get("/requests/")
        request.user = user
        return request

    return factory


@pytest.mark.django_db
@allure.feature("Права доступа")
@allure.story("Роли и группы")
class TestRoleGroups:
    """Роль — это набор разрешений, группы собираются из кода.

    Тесты:
      1. После migrate у каждой роли есть группа ровно с её разрешениями
      2. Пользователь попадает в группу своей роли и получает её права
      3. Смена роли переносит в другую группу, права прошлой роли пропадают
      4. Повторная синхронизация групп ничего не меняет
    """

    @pytest.mark.parametrize("role", ROLE_CASES)
    @allure.title("Группа роли {role} — ровно её разрешения")
    def test_group_matches_role_permissions(self, role):
        expected = {perm.codename for perm in ROLE_PERMISSIONS[role]}

        assert group_codenames(role) == expected

    @pytest.mark.parametrize("role", ROLE_CASES)
    @allure.title("Пользователь с ролью {role} получает права роли")
    def test_user_gets_role_permissions(self, make_user, role):
        user = make_user(role=role)

        assert list(user.groups.values_list("name", flat=True)) == [role.value]
        assert user.has_perms([str(perm) for perm in ROLE_PERMISSIONS[role]])

    @allure.title("Смена роли переносит пользователя в другую группу")
    def test_role_change_moves_group(self, make_user):
        user = make_user(role=Role.STUDENT)

        user.role = Role.TEACHER
        user.save()
        user = type(user).objects.get(pk=user.pk)  # сброс кэша прав

        assert list(user.groups.values_list("name", flat=True)) == [Role.TEACHER.value]
        assert user.has_perm(Perm.GRADE_SUBMISSIONS)
        assert not user.has_perm(Perm.SUBMIT_ASSIGNMENTS), "права студента должны пропасть"

    @allure.title("Синхронизация групп идемпотентна")
    def test_sync_is_idempotent(self):
        before = {role: group_codenames(role) for role in ROLE_PERMISSIONS}

        sync_role_groups()
        sync_role_groups()

        assert {role: group_codenames(role) for role in ROLE_PERMISSIONS} == before
        assert Group.objects.filter(name__in=Role.values).count() == len(Role)


@allure.feature("Права доступа")
@allure.story("require_perm")
class TestRequirePerm:
    """Декоратор прав на view.

    Тесты:
      1. Пользователь с правом проходит во view
      2. Вошедший без права получает 403
      3. Неактивный пользователь не проходит, даже если право есть
      4. Анонимного отправляют на вход с адресом возврата
      5. Ошибка при проверке прав — отказ, а не пропуск, с записью в лог
      6. Декоратор отмечает view разрешениями для сторожа
      7. require_perm без разрешений — ошибка конфигурации
    """

    @pytest.mark.django_db
    @allure.title("Пользователь с правом проходит во view")
    def test_allowed(self, protected_view, make_request, student):
        response = protected_view(make_request(student))

        assert response.status_code == 200

    @pytest.mark.django_db
    @allure.title("Вошедший без права получает 403")
    def test_denied_without_permission(self, protected_view, make_request, teacher):
        with pytest.raises(PermissionDenied):
            protected_view(make_request(teacher))

    @pytest.mark.django_db
    @allure.title("Неактивный пользователь не проходит")
    def test_inactive_user_denied(self, protected_view, make_request, make_user):
        user = make_user(role=Role.STUDENT, is_active=False)

        with pytest.raises(PermissionDenied):
            protected_view(make_request(user))

    @allure.title("Анонимного отправляют на вход")
    def test_anonymous_redirected_to_login(self, protected_view, make_request):
        response = protected_view(make_request(AnonymousUser()))

        assert response.status_code == 302
        assert response.url == "/login/?next=/requests/"

    @pytest.mark.django_db
    @allure.title("Ошибка при проверке прав — отказ и запись в лог")
    def test_fail_closed(self, protected_view, make_request, student, monkeypatch, caplog):
        def broken_has_perms(perms):
            raise RuntimeError("кэш прав недоступен")

        monkeypatch.setattr(student, "has_perms", broken_has_perms)

        with caplog.at_level(logging.ERROR), pytest.raises(PermissionDenied):
            protected_view(make_request(student))

        assert "кэш прав недоступен" in caplog.text

    @allure.title("View отмечен разрешениями для сторожа")
    def test_view_is_marked(self, protected_view):
        assert protected_view._required_perm == ("access.create_requests",)

    @allure.title("require_perm без разрешений — ошибка конфигурации")
    def test_requires_at_least_one_permission(self):
        with pytest.raises(ImproperlyConfigured, match="хотя бы одно"):
            require_perm()
