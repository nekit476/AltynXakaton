#!/usr/bin/env python
"""Точка входа Django: `uv run python manage.py <команда>` (или `uv run poe ...`)."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.dev")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
