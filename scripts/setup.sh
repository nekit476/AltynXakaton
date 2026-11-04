#!/usr/bin/env sh
# Настройка рабочего места одной командой (Linux, macOS, WSL):
#   1. ставит uv, если его нет;
#   2. `uv sync --locked` — Python из .python-version и зависимости из uv.lock в .venv;
#   3. scripts/bootstrap.py — .env под участника, git-хуки, проверка связи с БД.
# Повторный запуск безопасен.
#
#   ./scripts/setup.sh --dev b
set -eu

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
    echo "==> uv не найден — ставлю официальным установщиком (astral.sh)"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Установщик дописывает PATH для новых сессий; в этой добавляем сами.
    PATH="$HOME/.local/bin:$PATH"
    export PATH
fi

echo "==> uv sync: Python и зависимости в .venv"
if ! uv sync --locked; then
    echo "uv sync упал. Если uv.lock устарел — выполни 'uv lock' и закоммить его." >&2
    exit 1
fi

exec uv run python scripts/bootstrap.py "$@"
