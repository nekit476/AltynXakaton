"""PreToolUse-хук: не даёт агенту читать и править файлы с секретами (03_security.md §8).

Блокирует .env и .env.* (кроме .env.example), *.pem и всё в secrets/ — и прямым чтением
(Read/Edit/Write/Grep), и через команды оболочки. Код выхода 2 — Claude Code отменяет вызов
и показывает агенту причину из stderr.
"""

from __future__ import annotations

import json
import re
import sys

BLOCK_EXIT_CODE = 2

# .env или .env.<что угодно>, кроме .env.example — в начале пути или после разделителя.
ENV_FILE = re.compile(r"(^|[\s/\\'\"=])\.env(?!\.example\b)(\.[\w.-]+)?(?=$|[\s'\";|&)])")
PEM_FILE = re.compile(r"\.pem\b", re.IGNORECASE)
SECRETS_DIR = re.compile(r"(^|[\s/\\'\"])secrets[/\\]")
# Передать .env docker compose — не значит прочитать его в контекст агента.
ENV_FILE_FLAG = re.compile(r"--env-file[ =]\.env\b")

PATH_KEYS = ("file_path", "path", "notebook_path", "pattern", "glob")
COMMAND_TOOLS = ("Bash", "PowerShell")


def find_secret_reference(text: str) -> str | None:
    """Возвращает описание найденной ссылки на секрет или None."""
    if ENV_FILE.search(text):
        return ".env с секретами (шаблон — .env.example)"
    if PEM_FILE.search(text):
        return "ключ *.pem"
    if SECRETS_DIR.search(text):
        return "каталог secrets/"
    return None


def decide(payload: dict) -> str | None:
    """Причина блокировки вызова инструмента или None, если вызов можно пропустить."""
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    if tool in COMMAND_TOOLS:
        command = ENV_FILE_FLAG.sub("", str(tool_input.get("command", "")))
        return find_secret_reference(command)
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if value and (reason := find_secret_reference(str(value))):
            return reason
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Непонятный вход — не наш случай; ломать работу агента из-за этого не стоит.
        return 0
    reason = decide(payload)
    if reason is None:
        return 0
    print(
        f"Заблокировано хуком guard_secrets: {reason}. Секреты агенту не читать.", file=sys.stderr
    )
    return BLOCK_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
