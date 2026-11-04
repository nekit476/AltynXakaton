---
name: new-service
description: Добавить сервис или селектор в domain/ — сигнатура и DTO, тесты на правила, реализация, контракт для web. Использовать при новой бизнес-логике.
---

1. Сигнатура: первый аргумент — `user`, возврат — `@dataclass(frozen=True)` из `dto.py`,
   не модель. Чтение — `selectors.py`, запись — `services.py`.
2. Выборка ограничена пользователем (`for_student(user)`, `for_teacher(user)`).
   Чужой или несуществующий объект — `core.errors.NotFound`, а не `DoesNotExist`.
3. Своя ошибка — наследник `core.errors.AppError` с контекстом в атрибутах.
4. Сначала тесты в `tests/domain/<app>/` (parametrize на граничные случаи), потом реализация.
5. Запись — в `transaction.atomic`, задачи Celery — через `transaction.on_commit`.
6. Сигнатуру, которую уже использует `web`, не ломать: новые параметры — в конец, новые поля —
   в DTO. Изменение контракта — сообщить C.
7. `uv run poe test`, `uv run poe lint`, `uv run poe check`.
