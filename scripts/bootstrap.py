"""Первичная настройка рабочего места: .env под участника, git-хуки, проверка связи с БД.

Запускается из setup.ps1 / setup.sh, когда .venv уже собран, или командой `uv run poe setup`.
Повторный запуск безопасен: существующий .env не перезаписывается.

Django здесь не импортируется намеренно: пока нет .env, его настройки не собрать.
"""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE_PATH = ROOT / ".env.example"

# Скрипт только сообщает, доступна ли БД; ждать дольше незачем.
DB_CONNECT_TIMEOUT_S = 3
SECRET_KEY_BYTES = 50

# Без этих ключей сгенерированный .env не соберёт настройки Django.
REQUIRED_KEYS = ("DEV_PARTICIPANT", "DJANGO_SECRET_KEY", "DATABASE_URL")


@dataclass(frozen=True)
class Participant:
    """Участник команды и его личные ресурсы на общем сервере."""

    letter: str
    title: str
    module: str
    database: str
    redis_db: int


PARTICIPANTS = {
    "a": Participant("a", "платформа и качество (Никита)", "core", "dekanat_a", 1),
    "b": Participant("b", "учебная логика", "domain", "dekanat_b", 2),
    "c": Participant("c", "интерфейс и продукт", "web", "dekanat_c", 3),
}


class BootstrapError(Exception):
    """Настройку нельзя продолжить; текст ошибки — для человека."""


def _with_path(url: str, path: str) -> str:
    """Меняет в URL подключения только путь (имя базы или индекс Redis), сохраняя query."""
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{path}"))


def render_env(template: str, participant: Participant, secret_key: str) -> str:
    """Собирает .env участника из текста .env.example.

    Меняются только значения ключей участника: имя базы в DATABASE_URL, индекс в REDIS_URL,
    DJANGO_SECRET_KEY и DEV_PARTICIPANT. Комментарии и остальные строки переносятся как есть,
    чтобы .env оставался читаемым двойником шаблона.
    """
    replacements: dict[str, Callable[[str], str]] = {
        "DEV_PARTICIPANT": lambda _: participant.letter,
        "DJANGO_SECRET_KEY": lambda _: secret_key,
        "DATABASE_URL": lambda url: _with_path(url, participant.database),
        # Пустой REDIS_URL — осознанный режим «без Redis», его не трогаем.
        "REDIS_URL": lambda url: _with_path(url, str(participant.redis_db)) if url else url,
    }
    seen: set[str] = set()
    rendered: list[str] = []
    for line in template.splitlines(keepends=True):
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or line.lstrip().startswith("#") or key not in replacements:
            rendered.append(line)
            continue
        newline = "\n" if line.endswith("\n") else ""
        rendered.append(f"{key}={replacements[key](value.strip())}{newline}")
        seen.add(key)

    missing = [key for key in REQUIRED_KEYS if key not in seen]
    if missing:
        raise BootstrapError(f"в .env.example нет ключей: {', '.join(missing)}")
    return "".join(rendered)


def read_env_value(path: Path, key: str) -> str | None:
    """Достаёт одно значение из .env без Django (кавычки вокруг значения снимаются)."""
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#") and name.strip() == key:
            return value.strip().strip("'\"")
    return None


def check_database(url: str) -> str | None:
    """Пробует подключиться к PostgreSQL. Возвращает текст ошибки или None, если всё хорошо."""
    import psycopg  # импорт здесь: модуль должен импортироваться и без зависимостей проекта

    try:
        with psycopg.connect(url, connect_timeout=DB_CONNECT_TIMEOUT_S):
            return None
    except psycopg.Error as exc:
        # В тексте ошибки libpq нет пароля: только хост, порт и причина.
        return str(exc).strip()


def ask_participant() -> Participant:
    """Спрашивает букву участника в интерактивном терминале."""
    if not sys.stdin.isatty():
        raise BootstrapError("укажи участника: --dev a|b|c")
    menu = ", ".join(f"{p.letter} — {p.title}" for p in PARTICIPANTS.values())
    while True:
        answer = input(f"Кто ты? {menu}: ").strip().lower()
        if answer in PARTICIPANTS:
            return PARTICIPANTS[answer]
        print("Нужна одна буква: a, b или c.")


def ensure_env_file(letter: str | None) -> None:
    """Создаёт .env из шаблона, если его ещё нет. Существующий файл не трогает."""
    if ENV_PATH.exists():
        current = read_env_value(ENV_PATH, "DEV_PARTICIPANT")
        print(f"• .env уже есть (участник {current or '?'}), оставляю как есть.")
        if letter and current and letter != current:
            print(f"  Передан --dev {letter}. Чтобы пересоздать .env, удали его и запусти снова.")
        return
    participant = PARTICIPANTS[letter] if letter else ask_participant()
    template = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    content = render_env(template, participant, secrets.token_urlsafe(SECRET_KEY_BYTES))
    ENV_PATH.write_text(content, encoding="utf-8", newline="\n")
    print(
        f"• Создан .env: участник {participant.letter} ({participant.title}), "
        f"модуль {participant.module}/, база {participant.database}."
    )


def install_git_hooks() -> None:
    """Ставит pre-commit-хуки, если проект уже лежит в git-репозитории."""
    if not (ROOT / ".git").exists():
        print("• git-репозиторий не найден — хуки pre-commit пропущены.")
        return
    result = subprocess.run(
        [sys.executable, "-m", "pre_commit", "install", "--overwrite"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        # pre-commit пишет путь к Python в хук кодировкой системы (на русской Windows — cp1251),
        # а git-bash читает хук как UTF-8: путь с кириллицей («Хахатон») не находится, и коммит
        # падает с «pre-commit not found». PYTHONUTF8 заставляет записать хук в UTF-8.
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )
    if result.returncode == 0:
        print("• Хуки pre-commit установлены (ruff и проверки перед каждым коммитом).")
    else:
        print(f"• Хуки pre-commit не установились:\n{result.stderr.strip()}")


def report_database() -> bool:
    """Печатает, доступна ли база из DATABASE_URL. Возвращает True, если доступна."""
    url = read_env_value(ENV_PATH, "DATABASE_URL")
    if not url:
        print("• В .env нет DATABASE_URL — проверка БД пропущена.")
        return False
    error = check_database(url)
    if error is None:
        print(f"• База доступна: {urlsplit(url).hostname}{urlsplit(url).path}")
        return True
    print(
        "• База недоступна:\n"
        f"    {error}\n"
        "  Держишь БД у себя — запусти Docker Desktop и `uv run poe db-up`.\n"
        "  БД у коллеги или на сервере — открой SSH-туннель (PROJECT.md, «База данных»)."
    )
    return False


NEXT_STEPS = """
Дальше:
  uv run poe migrate    применить миграции к своей базе
  uv run poe dev        сервер на http://127.0.0.1:8000
  uv run poe test       тесты
  uv run poe            список всех команд
"""


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dev", choices=sorted(PARTICIPANTS), help="буква участника")
    parser.add_argument("--check-only", action="store_true", help="только проверить связь с БД")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    # Консоль Windows может не знать «ёлочек» и тире — пусть лучше будет «?», чем падение.
    sys.stdout.reconfigure(errors="replace")
    args = parse_args(argv)
    try:
        if args.check_only:
            return 0 if report_database() else 1
        ensure_env_file(args.dev)
        install_git_hooks()
        report_database()
    except BootstrapError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    print(NEXT_STEPS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
