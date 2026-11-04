"""Проверка запрещённых конструкций (scripts/check_forbidden.py)."""

import allure
import pytest

from scripts import check_forbidden
from scripts.check_forbidden import scan

FORBIDDEN_SAMPLES = [
    pytest.param("web/templates/a.html", "{{ text|safe }}", "|safe в шаблоне", id="safe-filter"),
    pytest.param("web/templates/a.html", "{{ text | safe }}", "|safe в шаблоне", id="safe-spaced"),
    pytest.param("web/views.py", "return mark_safe(html)", "mark_safe", id="mark-safe"),
    pytest.param("domain/org/selectors.py", "Group.objects.raw(sql)", "QuerySet.raw()", id="raw"),
    pytest.param("domain/org/selectors.py", "qs.extra(where=[w])", "QuerySet.extra()", id="extra"),
    pytest.param("web/templates/a.html", "<script>alert(1)</script>", "inline-скрипт", id="inline"),
    pytest.param("web/templates/a.html", '<button hx-on:click="x()">', "hx-on", id="hx-on"),
]

CLEAN_SAMPLES = [
    pytest.param("web/templates/a.html", "{{ text|safeseq_not }}", id="similar-filter-name"),
    pytest.param(
        "web/templates/a.html", '<script src="/static/js/app.js"></script>', id="script-src"
    ),
    pytest.param("web/templates/a.html", "{{ text|escape }}", id="escape"),
    pytest.param("domain/org/services.py", "draw(shape)", id="draw-is-not-raw"),
]


@pytest.fixture
def make_tree(tmp_path):
    """Кладёт один файл с указанным содержимым в подложенное дерево проекта."""

    def factory(relative: str, line: str):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{line}\n", encoding="utf-8")
        return tmp_path

    return factory


@allure.feature("Безопасность")
@allure.story("Запрещённые конструкции")
class TestCheckForbidden:
    """Сторож |safe, mark_safe, raw(), extra(), inline-скриптов и hx-on.

    Тесты:
      1. Каждая запрещённая конструкция находится, с файлом, строкой и правилом
      2. Похожие, но безопасные конструкции не считаются нарушением
      3. Исключение из ALLOWED пропускается, остальные правила для файла действуют
      4. В самом проекте запрещённых конструкций нет
    """

    @pytest.mark.parametrize(("relative", "line", "rule"), FORBIDDEN_SAMPLES)
    @allure.title("Находится нарушение «{rule}»: {line}")
    def test_violation_is_found(self, make_tree, relative, line, rule):
        root = make_tree(relative, line)

        violations = scan(root)

        assert [(v.path, v.line, v.rule) for v in violations] == [(relative, 1, rule)]

    @pytest.mark.parametrize(("relative", "line"), CLEAN_SAMPLES)
    @allure.title("Безопасная конструкция не считается нарушением: {line}")
    def test_clean_code_passes(self, make_tree, relative, line):
        root = make_tree(relative, line)

        assert scan(root) == []

    @allure.title("Исключение из ALLOWED действует только на своё правило")
    def test_allowed_exception(self, make_tree, monkeypatch):
        root = make_tree("web/templatetags/md.py", "mark_safe(clean); qs.raw(sql)")
        monkeypatch.setattr(
            check_forbidden,
            "ALLOWED",
            {("web/templatetags/md.py", "mark_safe"): "очищено nh3"},
        )

        violations = scan(root)

        assert [v.rule for v in violations] == ["QuerySet.raw()"]

    @allure.title("В коде проекта запрещённых конструкций нет")
    def test_project_is_clean(self):
        assert [str(v) for v in scan()] == []
