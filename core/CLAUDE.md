# core/ — участник 1 (A): платформа и качество

Настройки, пользователи, права, вход, аудит, экраны админа, служебные URL.

| Где | Что |
|---|---|
| `settings/base.py` | Общие настройки. Новое приложение — строка в `CORE_APPS`, `DOMAIN_APPS` или `WEB_APPS` |
| `settings/components.py` | Сборка БД и кэша из URL. Решения покрыты тестами `tests/core/test_settings_components.py` |
| `settings/dev.py`, `test.py`, `prod.py` | Отличия окружений |
| `users/` | `User` (UUID, `role`, `patronymic`) — `AUTH_USER_MODEL = "users.User"` |
| `health/` | `/health/` (жив ли процесс, без БД) и `/ready/` (БД и кэш) |
| `errors.py` | `AppError` → `NotFound`. Новые общие ошибки наследуются от `AppError` |
| `celery.py` | Приложение Celery. Настройки — `CELERY_*` в `settings/base.py` |

Будут: `access/` — `require_perm`, `Perm`, группы ролей (#13); `accounts/` — вход, argon2, axes (#12); `audit/` (#26); `adminpanel/` (#25, #39, #40).

## Правила

- Модель пользователя меняется только миграцией. `AUTH_USER_MODEL` не трогать.
- Настройка, которая отличается между машинами, приходит из переменной окружения и вносится в `.env.example`.
- `core` не импортирует `web`. Из `domain` берёт только селекторы, и только в `adminpanel` (статистика).
- Служебные адреса публичные (`@login_not_required`), в ответе нет хостов и текстов ошибок: детали пишутся только в лог.
