"""Сборка .env участника (scripts/bootstrap.py)."""

import allure
import pytest

from scripts.bootstrap import (
    ENV_EXAMPLE_PATH,
    PARTICIPANTS,
    BootstrapError,
    read_env_value,
    render_env,
)

SECRET = "generated-secret"

PARTICIPANT_CASES = [pytest.param(p, id=p.letter) for p in PARTICIPANTS.values()]

# Минимальный шаблон: проверяем правила подстановки, а не содержимое .env.example.
TEMPLATE = """\
# комментарий: DATABASE_URL=postgres://x@y/z
DJANGO_SECRET_KEY=placeholder
DEV_PARTICIPANT=a
DATABASE_URL=postgres://u:p@db.example.ru:5432/dekanat_a?sslmode=require
REDIS_URL=redis://:p@127.0.0.1:6379/1
OTHER=keep-me
"""


@allure.feature("Платформа")
@allure.story("Настройка рабочего места")
class TestRenderEnv:
    """.env из шаблона: у каждого участника своя база и свой Redis.

    Тесты:
      1. Настоящий .env.example собирается для каждого участника в его базу и индекс Redis
      2. Подставляется только нужное: хост, порт и query URL, комментарии и прочие ключи целы
      3. Пустой REDIS_URL остаётся пустым — режим без Redis
      4. Шаблон без обязательного ключа отвергается с названием ключа
    """

    # Здесь намеренно настоящий .env.example: он — часть контракта bootstrap, и тест
    # упадёт, если кто-то переименует в шаблоне ключ, на который опирается скрипт.
    @pytest.mark.parametrize("participant", PARTICIPANT_CASES)
    @allure.title("Шаблон .env.example собирается для участника {participant.letter}")
    def test_real_template_for_each_participant(self, tmp_path, participant):
        env_file = tmp_path / ".env"

        env_file.write_text(
            render_env(ENV_EXAMPLE_PATH.read_text(encoding="utf-8"), participant, SECRET),
            encoding="utf-8",
        )

        assert read_env_value(env_file, "DEV_PARTICIPANT") == participant.letter
        assert read_env_value(env_file, "DJANGO_SECRET_KEY") == SECRET
        assert read_env_value(env_file, "DATABASE_URL").endswith(f"/{participant.database}")
        assert read_env_value(env_file, "REDIS_URL").endswith(f"/{participant.redis_db}")

    @allure.title("Подставляются только значения участника")
    def test_only_participant_values_change(self):
        rendered = render_env(TEMPLATE, PARTICIPANTS["b"], SECRET)

        assert rendered.splitlines() == [
            "# комментарий: DATABASE_URL=postgres://x@y/z",
            f"DJANGO_SECRET_KEY={SECRET}",
            "DEV_PARTICIPANT=b",
            "DATABASE_URL=postgres://u:p@db.example.ru:5432/dekanat_b?sslmode=require",
            "REDIS_URL=redis://:p@127.0.0.1:6379/2",
            "OTHER=keep-me",
        ]

    @allure.title("Пустой REDIS_URL не превращается в адрес")
    def test_empty_redis_url_is_kept(self):
        template = TEMPLATE.replace("REDIS_URL=redis://:p@127.0.0.1:6379/1", "REDIS_URL=")

        rendered = render_env(template, PARTICIPANTS["c"], SECRET)

        assert "REDIS_URL=\n" in rendered

    @allure.title("Шаблон без DATABASE_URL отвергается")
    def test_missing_required_key(self):
        template = "\n".join(
            line for line in TEMPLATE.splitlines() if not line.startswith("DATABASE_URL")
        )

        with pytest.raises(BootstrapError, match="нет ключей: DATABASE_URL"):
            render_env(template, PARTICIPANTS["a"], SECRET)
