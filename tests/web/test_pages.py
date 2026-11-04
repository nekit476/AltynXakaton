"""Экраны-заглушки: кому открыты, кому нет, и что в навигации."""

import re

import allure
import pytest
from pytest_django.asserts import assertContains, assertNotContains

# (URL, роли с доступом, роли без доступа)
STUDENT = "student_client"
TEACHER = "teacher_client"
ADMIN = "administrator_client"
ALL_ROLES = (STUDENT, TEACHER, ADMIN)

PAGES = [
    pytest.param("/", ALL_ROLES, (), id="home"),
    pytest.param("/schedule/", ALL_ROLES, (), id="schedule"),
    pytest.param("/notifications/", ALL_ROLES, (), id="notifications"),
    pytest.param("/courses/", (STUDENT,), (TEACHER, ADMIN), id="courses"),
    pytest.param("/courses/optimization/", (STUDENT,), (TEACHER, ADMIN), id="course-detail"),
    pytest.param("/grades/", (STUDENT,), (TEACHER, ADMIN), id="grades"),
    pytest.param("/requests/", (STUDENT,), (TEACHER, ADMIN), id="requests"),
    pytest.param("/t/courses/", (TEACHER,), (STUDENT, ADMIN), id="teacher-courses"),
    pytest.param("/a/", (ADMIN,), (STUDENT, TEACHER), id="admin-overview"),
]


@allure.feature("Интерфейс")
@allure.story("Экраны-заглушки")
class TestPages:
    """Страницы для переключения между разделами.

    Тесты:
      1. Каждый экран открывается ролям с правом
      2. Остальные роли получают 403
      3. Аноним уходит на вход
      4. Несуществующий предмет — 404
      5. Навигация показывает пункты по правам роли
    """

    @pytest.mark.parametrize(("url", "allowed", "denied"), PAGES)
    @allure.title("{url}: открыт ролям с правом")
    def test_allowed_roles(self, request, url, allowed, denied):
        for fixture in allowed:
            response = request.getfixturevalue(fixture).get(url)

            assert response.status_code == 200, fixture

    @pytest.mark.parametrize(("url", "allowed", "denied"), PAGES)
    @allure.title("{url}: закрыт ролям без права")
    def test_denied_roles(self, request, login_client, make_user, url, allowed, denied):
        for fixture in denied:
            response = request.getfixturevalue(fixture).get(url)

            assert response.status_code == 403, fixture

    @pytest.mark.django_db
    @pytest.mark.parametrize(("url", "allowed", "denied"), PAGES)
    @allure.title("{url}: аноним уходит на вход")
    def test_anonymous(self, client, url, allowed, denied):
        response = client.get(url)

        assert response.status_code == 302
        assert response.url.startswith("/login/")

    @allure.title("Несуществующий предмет — 404")
    def test_unknown_course(self, student_client):
        assert student_client.get("/courses/no-such/").status_code == 404

    @allure.title("Студент видит учебные пункты меню, но не кабинеты преподавателя и админа")
    def test_student_navigation(self, student_client):
        response = student_client.get("/")

        for label in ("Расписание", "Предметы", "Оценки", "Заявки", "Уведомления"):
            assertContains(response, label)
        assertNotContains(response, "Мои курсы")
        assertNotContains(response, "Обзор")

    @allure.title("Преподаватель видит «Мои курсы», но не оценки студента")
    def test_teacher_navigation(self, teacher_client):
        response = teacher_client.get("/")

        assertContains(response, "Мои курсы")
        assertNotContains(response, "Оценки")

    @allure.title("Текущий раздел отмечен в меню")
    def test_current_page_marked(self, student_client):
        response = student_client.get("/grades/")

        # Ровно один пункт отмечен, и это «Оценки»; отступы в разметке не проверяем.
        html = response.content.decode()
        assert html.count('aria-current="page"') == 1
        assert re.search(r'aria-current="page">\s*Оценки</a>', html)
