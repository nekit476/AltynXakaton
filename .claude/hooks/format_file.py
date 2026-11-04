"""PostToolUse-хук: форматирует файл сразу после правки агентом.

.py — `ruff format` и `ruff check --fix`, .html — `djlint --reformat`. Те же инструменты,
что в pre-commit и CI, поэтому агент не накапливает замечаний линтера до коммита.
Ошибки форматтера работу не останавливают: их всё равно поймают pre-commit и CI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FORMATTERS: dict[str, list[list[str]]] = {
    ".py": [
        ["-m", "ruff", "format", "--force-exclude", "--quiet"],
        ["-m", "ruff", "check", "--fix", "--force-exclude", "--quiet"],
    ],
    ".html": [["-m", "djlint", "--reformat", "--quiet"]],
}


def commands_for(path: Path) -> list[list[str]]:
    return [[sys.executable, *args, str(path)] for args in FORMATTERS.get(path.suffix, [])]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path or not Path(file_path).is_file():
        return 0
    for command in commands_for(Path(file_path)):
        subprocess.run(command, check=False, capture_output=True)  # noqa: S603
    return 0


if __name__ == "__main__":
    sys.exit(main())
