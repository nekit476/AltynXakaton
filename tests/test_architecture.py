"""Границы четырёх модулей: core, domain, web, tests.

Сторож следит за тем, что договорённости из PROJECT.md соблюдаются кодом, а не памятью:
  * каждое приложение подключено в INSTALLED_APPS;
  * зависимость только web → domain, обратной нет;
  * web берёт данные через services / selectors / forms, а не напрямую из моделей.
"""

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import allure
import pytest
from django.apps import apps
from django.conf import settings

ROOT = Path(settings.BASE_DIR)
CODE_MODULES = ("core", "domain", "web")

# Запрещённые импорты: модуль, который проверяем → шаблон имени, которое ему импортировать нельзя.
WEB_PACKAGE = re.compile(r"^web(\.|$)")
DOMAIN_DATA_LAYER = re.compile(r"^domain\.\w+\.(models|managers)(\.|$)")


def python_files(module: str, root: Path = ROOT) -> Iterator[Path]:
    yield from sorted((root / module).rglob("*.py"))


def import_statements(path: Path) -> Iterator[tuple[int, set[str]]]:
    """Для каждого абсолютного импорта в файле: номер строки и все полные имена, которые он тянет.

    Для `from domain.org import models` это и `domain.org`, и `domain.org.models`:
    иначе импорт модуля моделей через from-форму прошёл бы мимо сторожа.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, {alias.name}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.lineno, {node.module} | {f"{node.module}.{a.name}" for a in node.names}


def find_violations(module: str, forbidden: re.Pattern[str], root: Path = ROOT) -> list[str]:
    """Одна запись на каждый запрещённый импорт: `файл:строка: имя`."""
    violations = []
    for path in python_files(module, root):
        for lineno, names in import_statements(path):
            matched = sorted(name for name in names if forbidden.search(name))
            if matched:
                violations.append(f"{path.relative_to(root)}:{lineno}: {matched[0]}")
    return violations


def discovered_apps() -> set[str]:
    """Dotted-имена всех пакетов с apps.py внутри модулей кода."""
    return {
        ".".join(path.parent.relative_to(ROOT).parts)
        for module in CODE_MODULES
        for path in (ROOT / module).rglob("apps.py")
    }


FORBIDDEN_IMPORT_SAMPLES = [
    pytest.param("domain", WEB_PACKAGE, "from web.views import home", id="domain-imports-web"),
    pytest.param("domain", WEB_PACKAGE, "import web.urls", id="domain-imports-web-module"),
    pytest.param(
        "web", DOMAIN_DATA_LAYER, "from domain.org.models import Group", id="web-imports-models"
    ),
    pytest.param("web", DOMAIN_DATA_LAYER, "from domain.org import models", id="web-from-models"),
    pytest.param(
        "web", DOMAIN_DATA_LAYER, "import domain.courses.managers", id="web-imports-managers"
    ),
]


@allure.feature("Архитектура")
@allure.story("Границы модулей")
class TestModuleBoundaries:
    """Модули не нарушают договорённостей о зависимостях.

    Тесты:
      1. Каждое приложение с apps.py из core/, domain/, web/ подключено в INSTALLED_APPS
      2. domain/ не импортирует web/
      3. web/ не импортирует модели и менеджеры domain/
      4. Сторож действительно ловит запрещённые импорты (самопроверка на подложенном файле)
      5. Разрешённые импорты сторож не трогает (самопроверка на подложенном файле)
    """

    @allure.title("Все приложения модулей подключены в INSTALLED_APPS")
    def test_all_apps_installed(self):
        installed = {config.name for config in apps.get_app_configs()}

        missing = discovered_apps() - installed

        assert not missing, f"Приложения не подключены в core/settings/base.py: {missing}"

    @allure.title("domain/ не зависит от web/")
    def test_domain_does_not_import_web(self):
        assert find_violations("domain", WEB_PACKAGE) == []

    @allure.title("web/ не лезет в модели domain/ в обход сервисов")
    def test_web_uses_services_not_models(self):
        assert find_violations("web", DOMAIN_DATA_LAYER) == []

    # Пока domain/ и web/ почти пусты, тесты 2–3 зеленели бы и со сломанным сторожем.
    # Самопроверка на подложенном файле доказывает, что он работает.
    @pytest.mark.parametrize(("module", "forbidden", "source"), FORBIDDEN_IMPORT_SAMPLES)
    @allure.title("Сторож ловит запрещённый импорт: {source}")
    def test_guard_catches_forbidden_import(self, tmp_path, module, forbidden, source):
        (tmp_path / module).mkdir()
        (tmp_path / module / "sample.py").write_text(source, encoding="utf-8")

        violations = find_violations(module, forbidden, root=tmp_path)

        assert len(violations) == 1
        assert violations[0].startswith(f"{module}")

    @allure.title("Сторож пропускает импорт сервисов и селекторов")
    def test_guard_allows_service_imports(self, tmp_path):
        (tmp_path / "web").mkdir()
        (tmp_path / "web" / "sample.py").write_text(
            "from domain.org import selectors, services\n"
            "from domain.org.forms import ProfileForm\n"
            "from core.errors import NotFound\n",
            encoding="utf-8",
        )

        assert find_violations("web", DOMAIN_DATA_LAYER, root=tmp_path) == []
