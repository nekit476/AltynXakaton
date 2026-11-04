#!/bin/sh
# Создаёт по базе на участника на общем сервере PostgreSQL: миграции из незаконченной
# ветки одного не ломают базу другого, а тестовые базы test_<имя> не пересекаются.
#
# Список — переменная DEV_DATABASES через запятую (dekanat_a,dekanat_b,dekanat_c).
# Скрипт запускается образом postgres один раз — при первой инициализации тома pgdata.
# Добавить базу позже: uv run poe db-psql → CREATE DATABASE dekanat_x;
#
# Скрипт подключается через source из entrypoint, поэтому без `set -u`/`exit`:
# они сломали бы сам entrypoint.

for db in $(echo "${DEV_DATABASES:-}" | tr ',' ' '); do
    case "$db" in
        *[!a-z0-9_]*)
            echo "10-dev-databases: пропускаю недопустимое имя базы '$db'" >&2
            continue
            ;;
    esac
    echo "10-dev-databases: создаю базу $db"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
        -c "CREATE DATABASE \"$db\" OWNER \"$POSTGRES_USER\";"
done
