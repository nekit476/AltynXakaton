---
name: new-view
description: Добавить новый view или HTMX-фрагмент в web/ — права, шаблон, URL, тесты. Использовать при любом новом адресе.
---

1. View в `web/` — тонкий: `@require_perm(Perm.…)` из `core.access` → селектор или сервис из
   `domain.<app>` → шаблон. Подходящего `Perm` нет — попроси A добавить его в
   `core/access/perms.py`; сам не выдумывай.
2. На `request.htmx` отдавай фрагмент `templates/<раздел>/_partials/…`, иначе — страницу целиком.
3. `core.errors.NotFound` → 404. Модели и менеджеры `domain` не импортировать.
4. URL — в `web/urls.py`, всегда с `name`: без имени адрес не попадёт в матрицу прав.
5. Публичный адрес — редкость: `@login_not_required` и строка в `core/access/public.py`
   с причиной; такой PR ревьюит A.
6. Тесты в `tests/web/`: роль с правом — 200 и нужный шаблон, роль без права — 403,
   аноним — переход на вход, HTMX-вариант, чужой объект — 404.
7. `uv run poe test` и `uv run poe lint` — зелёные. Сторож `tests/authz/test_guard.py` упадёт,
   если забыт `require_perm`.
