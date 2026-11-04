"""Тест-сторож: на каждом URL есть проверка прав (03_security.md §4).

Главный риск проекта — view или HTMX-фрагмент без проверки прав, написанный ИИ.
Сторож ловит его автоматически: новый URL без @require_perm не пройдёт CI.
"""

import allure
import pytest
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse
from django.urls import get_resolver, include, path

from core.access import Perm, require_perm
from core.access.public import AUTHENTICATED_ONLY_URL_NAMES, PUBLIC_URL_NAMES
from tests.authz.guard import all_url_names, find_unguarded


def plain_view(request):
    return HttpResponse()


@require_perm(Perm.VIEW_DASHBOARD)
def guarded_view(request):
    return HttpResponse()


# Отдельная функция, а не login_not_required(plain_view): декоратор Django не оборачивает
# view, а ставит атрибут на саму функцию — plain_view тоже стал бы «публичным».
@login_not_required
def public_view(request):
    return HttpResponse()


# Подложенные карты URL: какая ошибка в них должна найтись.
BROKEN_URLCONFS = [
    pytest.param([path("x/", plain_view, name="x")], "x: нет @require_perm", id="no-perm"),
    pytest.param([path("x/", guarded_view)], "у URL нет имени", id="no-name"),
    pytest.param(
        [path("h/", include(([path("x/", plain_view, name="x")], "nested")))],
        "nested:x: нет @require_perm",
        id="nested-namespace",
    ),
    pytest.param(
        [path("health/", include(([path("", plain_view, name="health")], "health")))],
        "health:health: публичный, но view без @login_not_required",
        id="public-without-marker",
    ),
]


@allure.feature("Права доступа")
@allure.story("Тест-сторож")
class TestGuard:
    """Каждый URL проекта защищён или явно объявлен публичным.

    Тесты:
      1. В проекте нет URL без require_perm и вне списка публичных
      2. Каждое имя из списков публичных и «только вход» существует в карте URL
      3. Сторож находит нарушения на подложенных картах URL (самопроверка)
      4. Защищённый и публичный view сторож пропускает (самопроверка)
      5. Django admin не на /admin/
    """

    @allure.title("В проекте нет незащищённых URL")
    def test_project_urls_are_guarded(self):
        assert find_unguarded(get_resolver().url_patterns) == []

    @allure.title("Списки публичных адресов не устарели")
    def test_allowlists_point_to_real_urls(self):
        names = all_url_names(get_resolver().url_patterns)

        assert (PUBLIC_URL_NAMES | AUTHENTICATED_ONLY_URL_NAMES) - names == set()

    @pytest.mark.parametrize(("urlconf", "expected"), BROKEN_URLCONFS)
    @allure.title("Сторож находит нарушение: {expected}")
    def test_guard_finds_violation(self, urlconf, expected):
        problems = find_unguarded(urlconf)

        assert len(problems) == 1
        assert expected in problems[0]

    @allure.title("Защищённый и публичный view сторож пропускает")
    def test_guard_accepts_correct_views(self):
        urlconf = [
            path("x/", guarded_view, name="x"),
            path("health/", include(([path("", public_view, name="health")], "health"))),
        ]

        assert find_unguarded(urlconf) == []

    @allure.title("Django admin не на /admin/")
    def test_django_admin_not_on_default_path(self, client, settings):
        response = client.get("/admin/")

        assert settings.DJANGO_ADMIN_PATH != "admin/"
        assert response.status_code == 404
