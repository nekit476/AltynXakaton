"""Хуки Claude Code: защита секретов и форматирование после правки (.claude/hooks)."""

import importlib.util
import io
import json
import sys
from pathlib import Path

import allure
import pytest
from django.conf import settings

HOOKS_DIR = Path(settings.BASE_DIR) / ".claude" / "hooks"


def load_hook(name: str):
    # .claude — не пакет Python (точка в имени), поэтому модуль грузится по пути.
    spec = importlib.util.spec_from_file_location(f"claude_hook_{name}", HOOKS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load_hook("guard_secrets")
formatter = load_hook("format_file")

BLOCKED = [
    pytest.param("Read", {"file_path": "C:/repo/.env"}, id="read-env"),
    pytest.param("Edit", {"file_path": "/repo/.env.local"}, id="edit-env-local"),
    pytest.param("Read", {"file_path": "/repo/infra/server.pem"}, id="read-pem"),
    pytest.param("Read", {"file_path": "/repo/secrets/token.txt"}, id="read-secrets-dir"),
    pytest.param("Grep", {"pattern": "PASSWORD", "path": ".env"}, id="grep-env"),
    pytest.param("Bash", {"command": "cat .env"}, id="bash-cat-env"),
    pytest.param("PowerShell", {"command": "Get-Content .\\.env"}, id="ps-get-content"),
    pytest.param("Bash", {"command": "grep KEY .env.prod"}, id="bash-env-prod"),
]

ALLOWED = [
    pytest.param("Read", {"file_path": "/repo/.env.example"}, id="read-example"),
    pytest.param("Read", {"file_path": "/repo/core/settings/base.py"}, id="read-code"),
    pytest.param("Bash", {"command": "uv run poe db-up"}, id="poe"),
    pytest.param(
        "Bash", {"command": "docker compose -f infra/compose.yml --env-file .env up"}, id="env-file"
    ),
    pytest.param("Bash", {"command": "cp .env.example /tmp/x"}, id="copy-example"),
    pytest.param("Read", {"file_path": "/repo/docs/environment.md"}, id="similar-name"),
]


@allure.feature("Работа с Claude")
@allure.story("Хуки")
class TestGuardSecrets:
    """PreToolUse-хук не пускает агента к секретам.

    Тесты:
      1. Чтение, правка и команды с .env, *.pem, secrets/ блокируются
      2. .env.example, код и передача .env в docker compose — разрешены
      3. Блокировка — код выхода 2 и причина в stderr
    """

    @pytest.mark.parametrize(("tool", "tool_input"), BLOCKED)
    @allure.title("Блокируется: {tool} {tool_input}")
    def test_blocked(self, tool, tool_input):
        assert guard.decide({"tool_name": tool, "tool_input": tool_input}) is not None

    @pytest.mark.parametrize(("tool", "tool_input"), ALLOWED)
    @allure.title("Разрешено: {tool} {tool_input}")
    def test_allowed(self, tool, tool_input):
        assert guard.decide({"tool_name": tool, "tool_input": tool_input}) is None

    @allure.title("Блокировка — код 2 и причина в stderr")
    def test_exit_code_and_message(self, monkeypatch, capsys):
        payload = {"tool_name": "Read", "tool_input": {"file_path": ".env"}}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

        code = guard.main()

        assert code == guard.BLOCK_EXIT_CODE
        assert ".env" in capsys.readouterr().err


@allure.feature("Работа с Claude")
@allure.story("Хуки")
class TestFormatFile:
    """PostToolUse-хук форматирует правленый файл.

    Тесты:
      1. Python-файл после правки отформатирован ruff
      2. Для неизвестного расширения форматтеров нет
    """

    @allure.title("Python-файл форматируется ruff")
    def test_python_file_is_formatted(self, tmp_path, monkeypatch):
        source = tmp_path / "sample.py"
        source.write_text("x=[1,2 ,3]\n", encoding="utf-8")
        payload = {"tool_name": "Edit", "tool_input": {"file_path": str(source)}}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

        assert formatter.main() == 0

        assert source.read_text(encoding="utf-8") == "x = [1, 2, 3]\n"

    @allure.title("Неизвестное расширение не трогается")
    def test_unknown_suffix(self):
        assert formatter.commands_for(Path("notes.txt")) == []
