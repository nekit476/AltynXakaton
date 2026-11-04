"""Ищет в коде запрещённые конструкции (03_security.md §2, §5, §10).

- `|safe` и `mark_safe` отключают автоэкранирование шаблонов — путь к XSS;
- `.raw(` и `.extra(` обходят параметризацию ORM — путь к SQL-инъекции;
- inline-скрипты и `hx-on` ломают строгий CSP (`script-src 'self'`).

Исключение разрешается только строкой в ALLOWED с причиной: так каждое видно на ревью.
Запуск: `uv run python scripts/check_forbidden.py` (входит в `uv run poe lint` и CI).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCANNED_MODULES = ("core", "domain", "web")


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]
    suffixes: tuple[str, ...]


RULES = (
    Rule("|safe в шаблоне", re.compile(r"\|\s*safe\b"), (".html",)),
    Rule("mark_safe", re.compile(r"\bmark_safe\b"), (".py", ".html")),
    Rule("QuerySet.raw()", re.compile(r"\.raw\("), (".py",)),
    Rule("QuerySet.extra()", re.compile(r"\.extra\("), (".py",)),
    # <script> без src — встроенный код; со src (файл из static/) — разрешён.
    Rule("inline-скрипт", re.compile(r"<script(?![^>]*\bsrc=)[^>]*>", re.IGNORECASE), (".html",)),
    Rule("hx-on", re.compile(r"\bhx-on\b|\bhx-on:", re.IGNORECASE), (".html",)),
)

# (путь от корня в POSIX-виде, имя правила) → почему можно. Пример на будущее:
# ("web/templatetags/markdown.py", "mark_safe"): "текст уже очищен nh3, см. 03_security.md §2 A05"
ALLOWED: dict[tuple[str, str], str] = {}


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str
    text: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.text}"


def scan_file(path: Path, root: Path = ROOT) -> list[Violation]:
    relative = path.relative_to(root).as_posix()
    rules = [rule for rule in RULES if path.suffix in rule.suffixes]
    violations = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for rule in rules:
            if rule.pattern.search(line) and (relative, rule.name) not in ALLOWED:
                violations.append(Violation(relative, number, rule.name, line.strip()))
    return violations


def scan(root: Path = ROOT, modules: tuple[str, ...] = SCANNED_MODULES) -> list[Violation]:
    suffixes = {suffix for rule in RULES for suffix in rule.suffixes}
    return [
        violation
        for module in modules
        for path in sorted((root / module).rglob("*"))
        if path.is_file() and path.suffix in suffixes
        for violation in scan_file(path, root)
    ]


def main() -> int:
    violations = scan()
    for violation in violations:
        print(violation)
    if violations:
        print(f"\nЗапрещённых конструкций: {len(violations)}. Правила — 03_security.md §10.")
        return 1
    print("Запрещённых конструкций нет.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
