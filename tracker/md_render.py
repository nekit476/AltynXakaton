"""Markdown-двойники трекеров и личных планов.

Excel и HTML удобны людям, а .md читается на GitHub, видна в диффе PR и
доступна агентам Claude без конвертации. Поэтому у каждого xlsx и html есть
md-версия, собранная из тех же данных:

- tracker/STATUS.md    — срез общего трекера (дашборд, этапы, функционал, блокеры, Гант);
- docs/plan/plan_X.md  — личный план (то же, что plan_X.html и лист «По_дням» личного xlsx).

Правила статусов здесь те же, что в формулах Excel. Меняешь одно — меняй и другое.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from people_notes import NOTES
from tracker_data import (
    DAYS_LIST,
    DEFAULT_STATE,
    DONE,
    FEATURE_BY_CODE,
    FEATURES,
    PEOPLE,
    STAGES,
    TASKS,
    Person,
    Stage,
    Task,
    TaskState,
    blockers,
    day,
    day_plan,
    stage_of_day,
    tasks_of,
)

WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
ACTIVE = ("В работе", "На ревью")
# Обозначения в текстовом Ганте. Двойные символы — чтобы столбец дня был шириной в число «04».
PLANNED, DONE_CELL, CO_CELL, EMPTY = "██", "▒▒", "░░", "··"


def dm(d: int) -> str:
    return f"{d:02d}.11"


def span(t: Task) -> str:
    return dm(t.start) if t.start == t.end else f"{dm(t.start)}–{dm(t.end)}"


def esc(text: object) -> str:
    """Экранирует символы, ломающие таблицу Markdown."""
    return str(text).replace("|", "\\|").replace("\n", " ")


def table(headers: list[str], rows: list[list[object]]) -> list[str]:
    if not rows:
        return ["_Нет записей._"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(esc(c) for c in row) + " |" for row in rows]
    return lines


def text_gantt(tasks: list[Task], cell: Callable[[Task, int], str]) -> list[str]:
    """Гант в моноширинном блоке: строка — задача, столбец — день.

    Название идёт после ячеек, поэтому кириллица разной длины не сбивает столбцы.
    """
    pad = " " * 9
    lines = ["```text",
             pad + " ".join(WEEKDAYS[day(d).weekday()] for d in DAYS_LIST),
             pad + " ".join(f"{d:02d}" for d in DAYS_LIST)]
    for t in tasks:
        cells = " ".join(cell(t, d) if t.start <= d <= t.end else EMPTY for d in DAYS_LIST)
        lines.append(f"#{t.id:<3} {t.owner:<3} {cells}  {t.title}")
    lines.append("```")
    return lines


# ---------------------------------------------------------------- правила статусов


def state_of(states: dict[int, TaskState], task_id: int) -> TaskState:
    return states.get(task_id, DEFAULT_STATE)


def is_overdue(task: Task, st: TaskState, today: date) -> bool:
    """Как столбец «Просрочено» в Excel: не готова, не отложена, а плановый конец прошёл."""
    return st.status not in (DONE, "Отложено") and day(task.end) < today


def stage_label(stage: Stage, pct: float, today: date) -> str:
    if pct == 1:
        return "Готово"
    if today > day(stage.end):
        return "Отстаём"
    if today >= day(stage.start):
        return "Идёт"
    return "Впереди"


def feature_label(total: int, done: int, active: int) -> str:
    if total == 0:
        return "—"
    if done == total:
        return "Готово"
    if done + active > 0:
        return "В работе"
    return "Не начато"


def blocker_label(blocking_status: str, waiting_start: int, today: date) -> str:
    if blocking_status == DONE:
        return "Снят"
    if today >= day(waiting_start):
        return "Мешает сейчас"
    return "Ожидается"


def pct(done: int, total: int) -> float:
    return done / total if total else 0.0


def fmt_pct(value: float) -> str:
    return f"{round(value * 100)} %"


# ---------------------------------------------------------------- STATUS.md


def status_md(states: dict[int, TaskState], today: date) -> str:
    """Срез общего трекера на дату сборки."""
    st = {t.id: state_of(states, t.id) for t in TASKS}
    done = [t for t in TASKS if st[t.id].status == DONE]
    active = [t for t in TASKS if st[t.id].status in ACTIVE]
    blocked = [t for t in TASKS if st[t.id].status == "Заблокировано"]
    overdue = [t for t in TASKS if is_overdue(t, st[t.id], today)]

    feat_rows, core_total, core_done = [], 0, 0
    for f in FEATURES:
        own = [t for t in TASKS if t.feature == f.code]
        f_done = sum(1 for t in own if st[t.id].status == DONE)
        f_active = sum(1 for t in own if st[t.id].status in ACTIVE)
        label = feature_label(len(own), f_done, f_active)
        if f.core:
            core_total += 1
            core_done += label == "Готово"
        feat_rows.append([f.code, f.title, "да" if f.core else "", f.moscow,
                          ", ".join(f"#{t.id}" for t in own), f"{f_done}/{len(own)}",
                          fmt_pct(pct(f_done, len(own))), label,
                          dm(max(t.end for t in own)) if own else "—"])

    all_b = blockers()
    b_rows = []
    for b in all_b:
        label = blocker_label(st[b.blocking.id].status, b.waiting.start, today)
        if label != "Снят":
            b_rows.append([label, f"#{b.waiting.id} {b.waiting.owner}", b.waiting.title, dm(b.waiting.start),
                           f"#{b.blocking.id} {b.blocking.owner}", dm(b.blocking.end), b.risk, b.plan_b])
    # Сначала то, что мешает прямо сейчас, затем по дате старта.
    b_rows.sort(key=lambda r: (r[0] != "Мешает сейчас", r[3]))
    now_blocking = sum(1 for r in b_rows if r[0] == "Мешает сейчас")

    lines = [
        "# Статус «Зачётки»",
        "",
        f"Срез на **{today:%d.%m.%Y}**. Собран командой `python tracker/build_trackers.py` из личных Excel-файлов "
        "(статусы ведут владельцы задач). Это текстовый двойник `Трекер_общий.xlsx`, руками не править.",
        "",
        "## Сводка",
        "",
        *table(["Показатель", "Значение"], [
            ["До финальной отправки", f"{max(0, (day(22) - today).days)} дн."],
            ["Готово задач", f"{len(done)} из {len(TASKS)} ({fmt_pct(pct(len(done), len(TASKS)))})"],
            ["В работе / на ревью", len(active)],
            ["Заблокировано", len(blocked)],
            ["Просрочено", len(overdue)],
            ["Ядро конкурса готово", f"{core_done} из {core_total} функций"],
            ["Блокеров мешает сейчас", now_blocking],
        ]),
        "",
        "## По этапам",
        "",
    ]
    stage_rows = []
    for s in STAGES:
        own = [t for t in TASKS if t.stage == s.code]
        s_done = sum(1 for t in own if st[t.id].status == DONE)
        p = pct(s_done, len(own))
        stage_rows.append([f"{s.code} {s.title}", f"{dm(s.start)}–{dm(s.end)}", dm(s.demo), len(own), s_done,
                           sum(1 for t in own if st[t.id].status in ACTIVE),
                           sum(1 for t in own if is_overdue(t, st[t.id], today)), fmt_pct(p),
                           stage_label(s, p, today)])
    lines += table(["Этап", "Даты", "Демо", "Задач", "Готово", "В работе", "Просроч.", "%", "Состояние"],
                   stage_rows)

    lines += ["", "## По людям (задачи, где человек — владелец)", ""]
    people_rows = []
    for p_ in PEOPLE:
        own = [t for t in TASKS if t.owner == p_.code]
        p_done = sum(1 for t in own if st[t.id].status == DONE)
        people_rows.append([f"{p_.code} — {p_.name} ({p_.role})", len(own), p_done, fmt_pct(pct(p_done, len(own))),
                            sum(1 for t in own if is_overdue(t, st[t.id], today)),
                            sum(1 for b in all_b if b.waiting.owner == p_.code and
                                blocker_label(st[b.blocking.id].status, b.waiting.start, today) == "Мешает сейчас")])
    lines += table(["Участник", "Задач", "Готово", "%", "Просрочено", "Блокеры сейчас"], people_rows)

    lines += ["", "## Какой функционал готов", "",
              "Функция готова, когда готовы все её задачи. «Ядро» — обязательная часть ТЗ конкурса.", ""]
    lines += table(["Код", "Функция", "Ядро", "MoSCoW", "Задачи", "Готово", "%", "Состояние", "План готовности"],
                   feat_rows)

    lines += ["", "## Открытые блокеры", "",
              "Задача ждёт чужую. Снятые (блокер готов) не показаны. Полный список с планом Б — лист «Блокеры».", ""]
    lines += table(["Состояние", "Ждёт", "Задача", "Начало", "Блокер", "План готовн.", "Риск", "План Б"], b_rows)

    lines += ["", "## Просроченные задачи", ""]
    lines += table(["ID", "Задача", "Кто", "План конец", "Статус"],
                   [[f"#{t.id}", t.title, t.owner, dm(t.end), st[t.id].status] for t in overdue])

    lines += ["", "## Все задачи", ""]
    lines += table(["ID", "Задача", "Кто", "Этап", "Даты", "Статус", "Факт", "Комментарий"],
                   [[t.id, t.title, t.owner + "".join(f"+{c}" for c in t.co), t.stage, span(t), st[t.id].status,
                     f"{st[t.id].fact:%d.%m}" if st[t.id].fact else "", st[t.id].comment or ""] for t in TASKS])

    lines += ["", "## Гант", "", f"`{PLANNED}` план · `{DONE_CELL}` готово · `{EMPTY}` вне плана", ""]
    lines += text_gantt(list(TASKS), lambda t, d: DONE_CELL if st[t.id].status == DONE else PLANNED)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- plan_X.md


def person_md(person: Person) -> str:
    """Личный план: то же, что plan_X.html, плюс план по дням из личного xlsx."""
    notes = NOTES[person.code]
    mine = tasks_of(person.code)
    owned = [t for t in mine if t.owner == person.code]
    all_b = blockers()
    incoming = [b for b in all_b if b.waiting.owner == person.code]
    outgoing = [b for b in all_b if b.blocking.owner == person.code]

    lines = [
        f"# План {person.code}: {person.role}",
        "",
        "> Концепт для конкурса «Цифровой деканат будущего». Файл генерируется "
        "`python tracker/build_pages.py` из `tracker/tracker_data.py` и `tracker/people_notes.py`; "
        f"HTML-версия — `plan_{person.code}.html`. Руками не править.",
        "",
        f"**{notes['mission']}**",
        "",
        f"{person.name}. {notes['why']}",
        "",
        *table(["Мои задачи", "Помогаю другим", "Блокеров с высоким риском", "Задач ждут меня"],
               [[len(owned), len(mine) - len(owned), sum(1 for b in incoming if b.risk == "Высокий"),
                 len({b.waiting.id for b in outgoing})]]),
        "",
        "## Мой путь",
        "",
        f"`{PLANNED}` я владелец · `{CO_CELL}` я участник (задача другого)",
        "",
        *text_gantt(mine, lambda t, d: PLANNED if t.owner == person.code else CO_CELL),
        "",
        "## По этапам",
        "",
        "Размер: S — до 2 часов, M — до дня. «если успеем» — опциональные задачи.",
    ]
    by_task = {}
    for b in incoming:
        by_task.setdefault(b.waiting.id, []).append(b)
    for s in STAGES:
        stage_tasks = [t for t in mine if t.stage == s.code]
        lines += ["", f"### {s.code} · {s.title} · {dm(s.start)}–{dm(s.end)} · демо {dm(s.demo)}", "",
                  f"{s.goal}.", ""]
        if not stage_tasks:
            lines.append("_В этом этапе своих задач нет._")
            continue
        for t in stage_tasks:
            marks = []
            if t.owner != person.code:
                marks.append(f"помогаю {t.owner}")
            if t.pri == "C":
                marks.append("если успеем")
            if t.id in by_task:
                worst = min(by_task[t.id], key=lambda b: b.slack_days)
                marks.append(f"риск: {worst.risk.lower()}")
            suffix = f" _({', '.join(marks)})_" if marks else ""
            lines.append(f"- **#{t.id}** {t.title} — {span(t)}, {t.size}, "
                         f"{FEATURE_BY_CODE[t.feature].title}{suffix}")
            if t.id in by_task:
                waits = ", ".join(f"#{b.blocking.id} ({b.blocking.owner}, {dm(b.blocking.end)})"
                                  for b in by_task[t.id])
                worst = min(by_task[t.id], key=lambda b: b.slack_days)
                lines.append(f"  - Жду {waits}. План Б: {worst.plan_b}")

    lines += ["", "## Блокеры", "",
              "Рассчитаны по зависимостям из бэклога. Запас < 0 — чужая задача по плану будет готова позже моего "
              "старта.", "", "### Я жду других", ""]
    lines += table(["Моя", "Задача", "Начинаю", "Жду", "Готово по плану", "Запас, дн", "Риск", "План Б"],
                   [[f"#{b.waiting.id}", b.waiting.title, dm(b.waiting.start), f"#{b.blocking.id} {b.blocking.owner}",
                     dm(b.blocking.end), b.slack_days, b.risk, b.plan_b] for b in incoming])
    lines += ["", "### Меня ждут", "",
              "Сдвигаешь срок такой задачи — предупреди того, кто ждёт, в тот же день, а не на синке.", ""]
    lines += table(["Моя", "Задача", "Мой срок", "Кто ждёт", "Они начинают", "Запас, дн", "Риск"],
                   [[f"#{b.blocking.id}", b.blocking.title, dm(b.blocking.end), f"#{b.waiting.id} {b.waiting.owner}",
                     dm(b.waiting.start), b.slack_days, b.risk] for b in outgoing])

    lines += ["", "## По дням", ""]
    day_rows = []
    for d in DAYS_LIST:
        stage = stage_of_day(d)
        todo = "; ".join(f"#{t.id} {t.title} — {action}" for t, action in day_plan(mine, d)) or "—"
        day_rows.append([f"{dm(d)} {WEEKDAYS[day(d).weekday()]}", stage.code,
                         "демо" if d == stage.demo else "", todo])
    lines += table(["День", "Этап", "", "Что делать"], day_rows)

    lines += ["", "## Моя зона", "", "**Владею кодом:**", ""]
    lines += [f"- `{z}`" for z in notes["zone"]]
    lines += ["", "**Ревьюю у других:**", ""]
    lines += [f"- {r}" for r in notes["reviews"]]

    lines += ["", "## Работа с Claude", ""]
    lines += [f"- **{a}** — {b}" for a, b in notes["claude"]]
    lines += ["", "**Первые промпты.** Это стартовые формулировки. Записывай в `docs/prompts.md`, как они "
              "звучали на самом деле, и что пришлось возвращать на доработку.", ""]
    for p_ in notes["prompts"]:
        lines += [f"> {p_}", ""]

    lines += ["## Старт и финиш", "", "**Первые два дня (4–5.11):**", ""]
    lines += [f"{i}. {x}" for i, x in enumerate(notes["first_day"], start=1)]
    lines += ["", "**Моя часть готова, когда:**", ""]
    lines += [f"- [ ] {x}" for x in notes["done"]]
    lines += ["", "**Пишу в PDF для жюри:**", ""]
    lines += [f"- {x}" for x in notes["pdf"]]

    lines += ["", "## Трекер", "",
              f"Статус отмечаешь в `tracker/{person.file_name}` (жёлтые ячейки листа «Мои_задачи»). На вечернем синке "
              "A запускает `python tracker/build_trackers.py`: общий Excel и `tracker/STATUS.md` подтягивают твои "
              "статусы."]
    return "\n".join(lines) + "\n"
