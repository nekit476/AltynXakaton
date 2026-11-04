"""Сборка Excel-трекеров «Зачётки»: общий + личные A, B, C.

Источник правды по статусам — личные файлы: каждый отмечает только свои
задачи (где он владелец). Общий трекер пересобирается из них и сам считает
прогресс по этапам, функционалу и людям.

    python build_trackers.py             # пересобрать общий из личных
                                         # (недостающие личные создаются)
    python build_trackers.py --personal  # ещё и пересобрать личные после правки
                                         # tracker_data.py, статусы сохраняются

Личные файлы по умолчанию не перезаписываются: их коммитят сами участники,
и лишняя пересборка дала бы конфликт бинарных файлов в git.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule, DataBarRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from md_render import status_md
from tracker_data import (
    DAYS_LIST,
    DEFAULT_STATE,
    DONE,
    FEATURES,
    PEOPLE,
    STAGES,
    STATUSES,
    SUBMIT_DAY,
    TASK_BY_ID,
    TASKS,
    Person,
    Task,
    TaskState,
    blockers,
    day,
    day_plan,
    dependents_of,
    stage_of_day,
    tasks_of,
)

HERE = Path(__file__).resolve().parent
GENERAL_FILE = "Трекер_общий.xlsx"
STATUS_FILE = "STATUS.md"

FONT = "Arial"
HEADER_ROW = 4  # строки 1–3 — заголовок листа и подсказка
FIRST = HEADER_ROW + 1
DAYS = DAYS_LIST
WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

HEADER_FILL = PatternFill("solid", fgColor="0E5C57")
INPUT_FILL = PatternFill("solid", fgColor="FFF4D6")  # ячейки, которые правит человек
MUTED_FILL = PatternFill("solid", fgColor="F2F2F2")
WEEKEND_FILL = PatternFill("solid", fgColor="EDEFEF")
THIN = Side(style="thin", color="D0D7D5")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# Цвет статуса: (заливка, шрифт). Пары взяты из стандартных стилей Excel —
# они читаются и в светлой, и в печатной версии.
STATUS_STYLE = {
    "В работе": ("FFEB9C", "9C5700"),
    "На ревью": ("DDEBF7", "1F4E78"),
    DONE: ("C6EFCE", "006100"),
    "Заблокировано": ("FFC7CE", "9C0006"),
    "Отложено": ("E7E6E6", "595959"),
}
OWNER_GANTT = {"A": "9FD3CD", "B": "C9B8F0", "C": "F6C690"}
DONE_GANTT = "63BE7B"




# ---------------------------------------------------------------- оформление


def cf_fill(color: str) -> PatternFill:
    """Заливка для условного форматирования. В dxf Excel берёт цвет из bgColor,
    а PatternFill(fgColor=...) его не задаёт — правило срабатывает, но без цвета."""
    return PatternFill(fill_type="solid", start_color=color, end_color=color)


def font(bold: bool = False, color: str = "000000", size: int = 10, italic: bool = False) -> Font:
    return Font(name=FONT, bold=bold, color=color, size=size, italic=italic)


def sheet_title(ws: Worksheet, title: str, hint: str) -> None:
    ws["A1"] = title
    ws["A1"].font = font(bold=True, size=14, color="0E5C57")
    ws["A2"] = hint
    ws["A2"].font = font(color="5B6B68", italic=True)


def header(ws: Worksheet, row: int, titles: list[str], widths: list[float]) -> None:
    for col, (title, width) in enumerate(zip(titles, widths, strict=True), start=1):
        cell = ws.cell(row=row, column=col, value=title)
        cell.font = font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = BORDER
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.row_dimensions[row].height = 30


def body_cell(ws: Worksheet, row: int, col: int, value, fmt: str | None = None, wrap: bool = False):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = font()
    cell.border = BORDER
    cell.alignment = Alignment(vertical="top", wrap_text=wrap)
    if fmt:
        cell.number_format = fmt
    return cell


def mark_input(ws: Worksheet, col_letters: str, first: int, last: int) -> None:
    for letter in col_letters:
        for row in range(first, last + 1):
            ws[f"{letter}{row}"].fill = INPUT_FILL


def status_rules(ws: Worksheet, rng: str) -> None:
    for status, (fill, color) in STATUS_STYLE.items():
        ws.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="equal",
                formula=[f'"{status}"'],
                fill=cf_fill(fill),
                font=Font(name=FONT, color=color, bold=status == DONE),
            ),
        )


def status_validation(ws: Worksheet, rng: str) -> None:
    dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=False)
    dv.error = "Выбери статус из списка"
    dv.errorTitle = "Неизвестный статус"
    ws.add_data_validation(dv)
    dv.add(rng)


def percent_bar(ws: Worksheet, rng: str) -> None:
    ws.conditional_formatting.add(
        rng,
        DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color=DONE_GANTT),
    )


def red_if_yes(ws: Worksheet, rng: str, first_cell: str) -> None:
    ws.conditional_formatting.add(
        rng,
        FormulaRule(formula=[f'{first_cell}="Да"'], font=Font(name=FONT, color="C00000", bold=True)),
    )


def risk_rules(ws: Worksheet, rng: str) -> None:
    for value, fill in (("Высокий", "FFC7CE"), ("Средний", "FFEB9C"), ("Низкий", "E2EFDA")):
        ws.conditional_formatting.add(
            rng, CellIsRule(operator="equal", formula=[f'"{value}"'], fill=cf_fill(fill))
        )


def deps_text(task: Task, other_only: bool = True) -> str:
    parts = []
    for dep_id in task.deps:
        dep = TASK_BY_ID[dep_id]
        if other_only and dep.owner == task.owner:
            continue
        parts.append(f"#{dep.id} ({dep.owner}, до {dep.end:02d}.11)")
    return "; ".join(parts)


def waiting_text(task: Task) -> str:
    return "; ".join(
        f"#{t.id} ({t.owner}, с {t.start:02d}.11)" for t in dependents_of(task.id) if t.owner != task.owner
    )


def task_risk(task: Task, all_blockers) -> str:
    order = {"Высокий": 3, "Средний": 2, "Низкий": 1}
    risks = [b.risk for b in all_blockers if b.waiting.id == task.id]
    return max(risks, key=order.__getitem__) if risks else ""


def overdue_formula(status_cell: str, end_cell: str) -> str:
    return f'=IF(AND({status_cell}<>"{DONE}",{status_cell}<>"Отложено",{end_cell}<TODAY()),"Да","")'


def gantt_sheet(ws: Worksheet, tasks: list[Task], source: str, id_rng: str, status_rng: str,
                start_rng: str, end_rng: str, color_by_owner: bool, person_code: str | None) -> None:
    """Гант: строки — задачи, столбцы — дни. Цвет считает условное форматирование
    по датам и статусу из листа-источника, поэтому «пройденный путь» виден сразу."""
    sheet_title(ws, "Гант: план и пройденный путь",
                "Цветом отмечены плановые дни задачи; зелёный — задача готова. Столбец сегодняшнего дня подсвечен.")
    fixed = ["ID", "Задача", "Кто", "Начало", "Конец", "Статус"]
    header(ws, HEADER_ROW, fixed + [""] * len(DAYS), [5, 46, 5, 8, 8, 12] + [4.2] * len(DAYS))
    first_day_col = len(fixed) + 1
    for i, d in enumerate(DAYS):
        col = first_day_col + i
        letter = get_column_letter(col)
        top = ws.cell(row=3, column=col, value=WEEKDAYS[day(d).weekday()])
        top.font = font(size=8, color="5B6B68")
        top.alignment = Alignment(horizontal="center")
        cell = ws.cell(row=HEADER_ROW, column=col, value=day(d))
        cell.number_format = "dd"
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[letter].width = 4.2
    last_row = FIRST + len(tasks) - 1
    for r, task in enumerate(tasks, start=FIRST):
        body_cell(ws, r, 1, task.id)
        body_cell(ws, r, 2, task.title)
        body_cell(ws, r, 3, task.owner)
        body_cell(ws, r, 4, f"=INDEX({source}!{start_rng},MATCH(A{r},{source}!{id_rng},0))", "dd.mm")
        body_cell(ws, r, 5, f"=INDEX({source}!{end_rng},MATCH(A{r},{source}!{id_rng},0))", "dd.mm")
        body_cell(ws, r, 6, f"=INDEX({source}!{status_rng},MATCH(A{r},{source}!{id_rng},0))")
        for i in range(len(DAYS)):
            body_cell(ws, r, first_day_col + i, None)
    first_l = get_column_letter(first_day_col)
    last_l = get_column_letter(first_day_col + len(DAYS) - 1)
    grid = f"{first_l}{FIRST}:{last_l}{last_row}"
    in_plan = f"AND({first_l}${HEADER_ROW}>=$D{FIRST},{first_l}${HEADER_ROW}<=$E{FIRST})"
    # Порядок правил важен: «готово» перекрывает цвет владельца.
    ws.conditional_formatting.add(grid, FormulaRule(
        formula=[f'AND({in_plan},$F{FIRST}="{DONE}")'], fill=cf_fill(DONE_GANTT), stopIfTrue=True))
    if color_by_owner:
        for code, color in OWNER_GANTT.items():
            ws.conditional_formatting.add(grid, FormulaRule(
                formula=[f'AND({in_plan},$C{FIRST}="{code}")'], fill=cf_fill(color)))
    else:
        ws.conditional_formatting.add(grid, FormulaRule(
            formula=[in_plan], fill=cf_fill(OWNER_GANTT[person_code or "A"])))
    ws.conditional_formatting.add(
        f"{first_l}{HEADER_ROW}:{last_l}{last_row}",
        FormulaRule(formula=[f"{first_l}${HEADER_ROW}=TODAY()"], border=Border(left=Side("medium", "C76A12"),
                                                                                right=Side("medium", "C76A12"))))
    status_rules(ws, f"F{FIRST}:F{last_row}")
    ws.freeze_panes = ws.cell(row=FIRST, column=first_day_col)


# ---------------------------------------------------------------- общий файл


def build_general(states: dict[int, TaskState]) -> Workbook:
    wb = Workbook()
    dash = wb.active
    dash.title = "Дашборд"
    tasks_ws = wb.create_sheet("Задачи")
    stages_ws = wb.create_sheet("Этапы")
    feat_ws = wb.create_sheet("Функционал")
    block_ws = wb.create_sheet("Блокеры")
    gantt_ws = wb.create_sheet("Гант")
    help_ws = wb.create_sheet("Справка")

    last = FIRST + len(TASKS) - 1
    rng = {c: f"${c}${FIRST}:${c}${last}" for c in "ACEFLMO"}
    all_blockers = blockers()

    # --- Задачи
    sheet_title(tasks_ws, "Все задачи",
                "Статусы сюда приходят из личных файлов (python build_trackers.py). Жёлтые столбцы правит человек.")
    header(tasks_ws, HEADER_ROW,
           ["ID", "Задача", "Владелец", "Участвуют", "Этап", "Фича", "Функция", "Приоритет", "Размер",
            "Зависит от", "План начало", "План конец", "Статус", "Факт готово", "Просрочено",
            "Ждёт от других", "Комментарий"],
           [5, 52, 9, 10, 6, 6, 32, 9, 7, 12, 10, 10, 13, 11, 10, 30, 30])
    tasks_ws["K4"].comment = Comment("Плановые даты — из docs/plan/06_team_roadmap.md и 07_backlog.md", "plan")
    for r, t in enumerate(TASKS, start=FIRST):
        st = states.get(t.id, DEFAULT_STATE)
        values = [t.id, t.title, t.owner, ", ".join(t.co), t.stage, t.feature,
                  next(f.title for f in FEATURES if f.code == t.feature), t.pri, t.size,
                  ", ".join(f"#{d}" for d in t.deps), day(t.start), day(t.end), st.status, st.fact,
                  overdue_formula(f"M{r}", f"L{r}"), deps_text(t), st.comment]
        for col, value in enumerate(values, start=1):
            fmt = "dd.mm" if col in (11, 12, 14) else None
            body_cell(tasks_ws, r, col, value, fmt, wrap=col in (2, 16, 17))
    mark_input(tasks_ws, "MNQ", FIRST, last)
    status_validation(tasks_ws, f"M{FIRST}:M{last}")
    status_rules(tasks_ws, f"M{FIRST}:M{last}")
    red_if_yes(tasks_ws, f"O{FIRST}:O{last}", f"O{FIRST}")
    tasks_ws.auto_filter.ref = f"A{HEADER_ROW}:Q{last}"
    tasks_ws.freeze_panes = f"C{FIRST}"

    # --- Этапы
    sheet_title(stages_ws, "Прогресс по этапам", "Всё считается формулами из листа «Задачи».")
    header(stages_ws, HEADER_ROW,
           ["Этап", "Название", "Начало", "Конец", "Цель", "Демо", "Задач", "Готово", "В работе",
            "Заблок.", "Просроч.", "Готово, %", "Состояние"],
           [6, 22, 9, 9, 52, 8, 7, 8, 9, 8, 9, 11, 12])
    for r, s in enumerate(STAGES, start=FIRST):
        crit = f'Задачи!{rng["E"]},A{r}'
        values = [s.code, s.title, day(s.start), day(s.end), s.goal, day(s.demo),
                  f"=COUNTIF({crit})",
                  f'=COUNTIFS({crit},Задачи!{rng["M"]},"{DONE}")',
                  f'=COUNTIFS({crit},Задачи!{rng["M"]},"В работе")+COUNTIFS({crit},Задачи!{rng["M"]},"На ревью")',
                  f'=COUNTIFS({crit},Задачи!{rng["M"]},"Заблокировано")',
                  f'=COUNTIFS({crit},Задачи!{rng["O"]},"Да")',
                  f"=IF(G{r}=0,0,H{r}/G{r})",
                  f'=IF(L{r}=1,"Готово",IF(TODAY()>D{r},"Отстаём",IF(TODAY()>=C{r},"Идёт","Впереди")))']
        for col, value in enumerate(values, start=1):
            fmt = "dd.mm" if col in (3, 4, 6) else ("0%" if col == 12 else None)
            body_cell(stages_ws, r, col, value, fmt, wrap=col == 5)
    s_last = FIRST + len(STAGES) - 1
    tot = s_last + 1
    body_cell(stages_ws, tot, 1, "Итого").font = font(bold=True)
    for col in "GHIJK":
        body_cell(stages_ws, tot, ord(col) - 64, f"=SUM({col}{FIRST}:{col}{s_last})").font = font(bold=True)
    body_cell(stages_ws, tot, 12, f"=IF(G{tot}=0,0,H{tot}/G{tot})", "0%").font = font(bold=True)
    percent_bar(stages_ws, f"L{FIRST}:L{tot}")
    for value, fill in (("Готово", "C6EFCE"), ("Отстаём", "FFC7CE"), ("Идёт", "FFEB9C")):
        stages_ws.conditional_formatting.add(f"M{FIRST}:M{s_last}", CellIsRule(
            operator="equal", formula=[f'"{value}"'], fill=cf_fill(fill)))

    # --- Функционал
    sheet_title(feat_ws, "Какой функционал готов",
                "Функция готова, когда готовы все её задачи. «Ядро» — обязательная часть ТЗ конкурса.")
    header(feat_ws, HEADER_ROW,
           ["Код", "Функция", "Ядро", "MoSCoW", "Кто делает", "Задачи", "Всего", "Готово", "В работе",
            "Готово, %", "Состояние", "План готовности", "Отстаёт"],
           [6, 40, 7, 8, 11, 28, 7, 8, 9, 11, 12, 12, 9])
    for r, f in enumerate(FEATURES, start=FIRST):
        own = [t for t in TASKS if t.feature == f.code]
        crit = f'Задачи!{rng["F"]},A{r}'
        values = [f.code, f.title, "Да" if f.core else "—", f.moscow,
                  ", ".join(sorted({t.owner for t in own} | {c for t in own for c in t.co})),
                  ", ".join(f"#{t.id}" for t in own),
                  f"=COUNTIF({crit})",
                  f'=COUNTIFS({crit},Задачи!{rng["M"]},"{DONE}")',
                  f'=COUNTIFS({crit},Задачи!{rng["M"]},"В работе")+COUNTIFS({crit},Задачи!{rng["M"]},"На ревью")',
                  f"=IF(G{r}=0,0,H{r}/G{r})",
                  f'=IF(G{r}=0,"—",IF(J{r}=1,"Готово",IF(H{r}+I{r}>0,"В работе","Не начато")))',
                  f"=_xlfn.MAXIFS(Задачи!{rng['L']},{crit})",
                  f'=IF(AND(K{r}<>"Готово",TODAY()>L{r}),"Да","")']
        for col, value in enumerate(values, start=1):
            fmt = "0%" if col == 10 else ("dd.mm" if col == 12 else None)
            body_cell(feat_ws, r, col, value, fmt, wrap=col in (2, 6))
    f_last = FIRST + len(FEATURES) - 1
    percent_bar(feat_ws, f"J{FIRST}:J{f_last}")
    status_rules(feat_ws, f"K{FIRST}:K{f_last}")
    red_if_yes(feat_ws, f"M{FIRST}:M{f_last}", f"M{FIRST}")
    feat_ws.conditional_formatting.add(f"C{FIRST}:C{f_last}", CellIsRule(
        operator="equal", formula=['"Да"'], font=Font(name=FONT, bold=True, color="C76A12")))
    feat_ws.auto_filter.ref = f"A{HEADER_ROW}:M{f_last}"
    feat_ws.freeze_panes = f"C{FIRST}"

    # --- Блокеры
    sheet_title(block_ws, "Блокеры между участниками",
                "Задача ждёт чужую. Запас < 0 — блокер будет готов позже начала: сразу работать по плану Б.")
    header(block_ws, HEADER_ROW,
           ["Ждёт", "Задача", "Кто", "Начало", "Блокер", "Задача-блокер", "Чья", "План готовн.",
            "Запас, дн", "Риск", "Статус блокера", "Состояние", "План Б"],
           [6, 40, 5, 9, 7, 40, 5, 11, 9, 9, 13, 14, 50])
    for r, b in enumerate(all_blockers, start=FIRST):
        lookup = "=INDEX(Задачи!{col},MATCH({key},Задачи!" + rng["A"] + ",0))"
        start_rng = f"$K${FIRST}:$K${last}"
        values = [b.waiting.id, b.waiting.title, b.waiting.owner, lookup.format(col=start_rng, key=f"A{r}"),
                  b.blocking.id, b.blocking.title, b.blocking.owner, lookup.format(col=rng["L"], key=f"E{r}"),
                  f"=D{r}-H{r}-1",
                  f'=IF(I{r}<0,"Высокий",IF(I{r}=0,"Средний","Низкий"))',
                  lookup.format(col=rng["M"], key=f"E{r}"),
                  f'=IF(K{r}="{DONE}","Снят",IF(TODAY()>=D{r},"Мешает сейчас","Ожидается"))',
                  b.plan_b]
        for col, value in enumerate(values, start=1):
            body_cell(block_ws, r, col, value, "dd.mm" if col in (4, 8) else None, wrap=col in (2, 6, 13))
    b_last = FIRST + len(all_blockers) - 1
    risk_rules(block_ws, f"J{FIRST}:J{b_last}")
    status_rules(block_ws, f"K{FIRST}:K{b_last}")
    for value, fill in (("Снят", "C6EFCE"), ("Мешает сейчас", "FFC7CE")):
        block_ws.conditional_formatting.add(f"L{FIRST}:L{b_last}", CellIsRule(
            operator="equal", formula=[f'"{value}"'], fill=cf_fill(fill)))
    block_ws.auto_filter.ref = f"A{HEADER_ROW}:M{b_last}"
    block_ws.freeze_panes = f"C{FIRST}"

    # --- Дашборд
    sheet_title(dash, "«Зачётка» — общий трекер", "Сводка считается формулами. Ничего здесь не правь руками.")
    dash.column_dimensions["A"].width = 30
    for letter, width in zip("BCDEFG", (12, 12, 12, 12, 14, 14), strict=True):
        dash.column_dimensions[letter].width = width
    kv = [
        ("Сегодня", "=TODAY()", "dd.mm.yyyy"),
        ("До финальной отправки, дней", f"=MAX(0,DATE(2026,11,{SUBMIT_DAY})-TODAY())", "0"),
        ("Задач всего", f"=COUNTA(Задачи!{rng['A']})", "0"),
        ("Готово", f'=COUNTIF(Задачи!{rng["M"]},"{DONE}")', "0"),
        ("Общий прогресс", "=IF(B6=0,0,B7/B6)", "0%"),
        ("В работе / на ревью", f'=COUNTIF(Задачи!{rng["M"]},"В работе")+COUNTIF(Задачи!{rng["M"]},"На ревью")', "0"),
        ("Заблокировано", f'=COUNTIF(Задачи!{rng["M"]},"Заблокировано")', "0"),
        ("Просрочено", f'=COUNTIF(Задачи!{rng["O"]},"Да")', "0"),
        ("Функций ядра конкурса готово", f'=COUNTIFS(Функционал!$C${FIRST}:$C${f_last},"Да",'
                                         f'Функционал!$K${FIRST}:$K${f_last},"Готово")', "0"),
        ("Функций в ядре", f'=COUNTIF(Функционал!$C${FIRST}:$C${f_last},"Да")', "0"),
        ("Ядро конкурса готово", "=IF(B13=0,0,B12/B13)", "0%"),
        ("Блокеров мешает сейчас", f'=COUNTIF(Блокеры!$L${FIRST}:$L${b_last},"Мешает сейчас")', "0"),
    ]
    for i, (label, formula, fmt) in enumerate(kv, start=4):
        body_cell(dash, i, 1, label)
        body_cell(dash, i, 2, formula, fmt).font = font(bold=True)
    percent_bar(dash, "B8")
    percent_bar(dash, "B14")
    for cell in ("B10", "B11", "B15"):
        dash.conditional_formatting.add(cell, CellIsRule(
            operator="greaterThan", formula=["0"], font=Font(name=FONT, bold=True, color="C00000")))

    row = 18
    dash.cell(row=row, column=1, value="По этапам").font = font(bold=True, size=12, color="0E5C57")
    header(dash, row + 1, ["Этап", "Конец", "Готово, %", "Состояние"], [30, 12, 12, 12])
    for i in range(len(STAGES)):
        r = row + 2 + i
        src = FIRST + i
        body_cell(dash, r, 1, f'=Этапы!A{src}&" "&Этапы!B{src}')
        body_cell(dash, r, 2, f"=Этапы!D{src}", "dd.mm")
        body_cell(dash, r, 3, f"=Этапы!L{src}", "0%")
        body_cell(dash, r, 4, f"=Этапы!M{src}")
    stage_rows = f"C{row + 2}:C{row + 1 + len(STAGES)}"
    percent_bar(dash, stage_rows)

    row = row + 3 + len(STAGES)
    dash.cell(row=row, column=1, value="По людям (задачи, где человек — владелец)").font = font(
        bold=True, size=12, color="0E5C57")
    header(dash, row + 1, ["Участник", "Задач", "Готово", "Готово, %", "Просрочено", "Блокеры сейчас"],
           [30, 12, 12, 12, 12, 14])
    for i, p in enumerate(PEOPLE):
        r = row + 2 + i
        body_cell(dash, r, 1, f"{p.code} — {p.name} ({p.role})")
        body_cell(dash, r, 2, f'=COUNTIF(Задачи!{rng["C"]},"{p.code}")')
        body_cell(dash, r, 3, f'=COUNTIFS(Задачи!{rng["C"]},"{p.code}",Задачи!{rng["M"]},"{DONE}")')
        body_cell(dash, r, 4, f"=IF(B{r}=0,0,C{r}/B{r})", "0%")
        body_cell(dash, r, 5, f'=COUNTIFS(Задачи!{rng["C"]},"{p.code}",Задачи!{rng["O"]},"Да")')
        body_cell(dash, r, 6, f'=COUNTIFS(Блокеры!$C${FIRST}:$C${b_last},"{p.code}",'
                              f'Блокеры!$L${FIRST}:$L${b_last},"Мешает сейчас")')
    percent_bar(dash, f"D{row + 2}:D{row + 1 + len(PEOPLE)}")

    # --- Гант и справка
    gantt_sheet(gantt_ws, list(TASKS), "Задачи", rng["A"], rng["M"], f"$K${FIRST}:$K${last}", rng["L"],
                color_by_owner=True, person_code=None)
    help_sheet(help_ws, general=True)
    wb.calculation.fullCalcOnLoad = True
    return wb


# ---------------------------------------------------------------- личный файл


def build_personal(person: Person, states: dict[int, TaskState]) -> Workbook:
    wb = Workbook()
    mine_ws = wb.active
    mine_ws.title = "Мои_задачи"
    block_ws = wb.create_sheet("Блокеры")
    days_ws = wb.create_sheet("По_дням")
    gantt_ws = wb.create_sheet("Гант")
    progress_ws = wb.create_sheet("Прогресс")
    help_ws = wb.create_sheet("Справка")

    mine = tasks_of(person.code)
    last = FIRST + len(mine) - 1
    all_blockers = blockers()

    sheet_title(mine_ws, f"{person.code} — {person.name}: {person.role}",
                "Отмечай статус и дату готовности в жёлтых ячейках. Серые строки — задачи, где ты участник: "
                "статус ведёт владелец.")
    header(mine_ws, HEADER_ROW,
           ["ID", "Задача", "Роль", "Этап", "Функция", "Приор.", "Размер", "План начало", "План конец",
            "Статус", "Факт готово", "Просрочено", "Жду от других", "Риск", "План Б", "Меня ждут",
            "Комментарий"],
           [5, 50, 10, 6, 28, 7, 7, 10, 10, 13, 11, 10, 26, 9, 44, 24, 28])
    for r, t in enumerate(mine, start=FIRST):
        st = states.get(t.id, DEFAULT_STATE)
        is_owner = t.owner == person.code
        incoming = [b for b in all_blockers if b.waiting.id == t.id]
        values = [t.id, t.title, "Владелец" if is_owner else f"Участник ({t.owner})", t.stage,
                  next(f.title for f in FEATURES if f.code == t.feature), t.pri, t.size,
                  day(t.start), day(t.end), st.status, st.fact, overdue_formula(f"J{r}", f"I{r}"),
                  deps_text(t), task_risk(t, all_blockers), "; ".join(b.plan_b for b in incoming),
                  waiting_text(t), st.comment]
        for col, value in enumerate(values, start=1):
            fmt = "dd.mm" if col in (8, 9, 11) else None
            cell = body_cell(mine_ws, r, col, value, fmt, wrap=col in (2, 13, 15, 16, 17))
            if not is_owner:
                cell.fill = MUTED_FILL
                cell.font = font(italic=True, color="595959")
        if is_owner:
            mark_input(mine_ws, "JKQ", r, r)
    status_validation(mine_ws, f"J{FIRST}:J{last}")
    status_rules(mine_ws, f"J{FIRST}:J{last}")
    red_if_yes(mine_ws, f"L{FIRST}:L{last}", f"L{FIRST}")
    risk_rules(mine_ws, f"N{FIRST}:N{last}")
    mine_ws.auto_filter.ref = f"A{HEADER_ROW}:Q{last}"
    mine_ws.freeze_panes = f"C{FIRST}"
    src = "Мои_задачи"
    id_rng, status_rng = f"$A${FIRST}:$A${last}", f"$J${FIRST}:$J${last}"

    # --- Блокеры: входящие и исходящие
    sheet_title(block_ws, "Мои блокеры",
                "Сверху — чего жду я (и что делаю, пока жду). Снизу — кто ждёт меня: сдвигаешь срок — "
                "предупреди его заранее.")
    header(block_ws, HEADER_ROW,
           ["Моя задача", "Что", "Начинаю", "Жду #", "Чего жду", "От кого", "Готово по плану",
            "Запас, дн", "Риск", "Статус блокера (с синка)", "План Б"],
           [8, 40, 10, 7, 40, 8, 12, 9, 9, 16, 50])
    incoming = [b for b in all_blockers if b.waiting.owner == person.code]
    for r, b in enumerate(incoming, start=FIRST):
        values = [b.waiting.id, b.waiting.title, day(b.waiting.start), b.blocking.id, b.blocking.title,
                  b.blocking.owner, day(b.blocking.end), f"=C{r}-G{r}-1",
                  f'=IF(H{r}<0,"Высокий",IF(H{r}=0,"Средний","Низкий"))', STATUSES[0], b.plan_b]
        for col, value in enumerate(values, start=1):
            body_cell(block_ws, r, col, value, "dd.mm" if col in (3, 7) else None, wrap=col in (2, 5, 11))
    in_last = FIRST + max(len(incoming), 1) - 1
    if incoming:
        mark_input(block_ws, "J", FIRST, in_last)
        status_validation(block_ws, f"J{FIRST}:J{in_last}")
        status_rules(block_ws, f"J{FIRST}:J{in_last}")
        risk_rules(block_ws, f"I{FIRST}:I{in_last}")

    out_title = in_last + 3
    block_ws.cell(row=out_title, column=1, value="Меня ждут").font = font(bold=True, size=12, color="0E5C57")
    out_header = out_title + 1
    header(block_ws, out_header,
           ["Моя задача", "Что", "Мой срок", "Кто ждёт", "Их задача #", "Что у них", "Они начинают",
            "Запас, дн", "Риск", "", ""],
           [8, 40, 10, 7, 40, 8, 12, 9, 9, 16, 50])
    outgoing = [b for b in all_blockers if b.blocking.owner == person.code]
    for r, b in enumerate(outgoing, start=out_header + 1):
        values = [b.blocking.id, b.blocking.title, day(b.blocking.end), b.waiting.owner, b.waiting.id,
                  b.waiting.title, day(b.waiting.start), f"=G{r}-C{r}-1",
                  f'=IF(H{r}<0,"Высокий",IF(H{r}=0,"Средний","Низкий"))']
        for col, value in enumerate(values, start=1):
            body_cell(block_ws, r, col, value, "dd.mm" if col in (3, 7) else None, wrap=col in (2, 6))
    if outgoing:
        out_last = out_header + len(outgoing)
        risk_rules(block_ws, f"I{out_header + 1}:I{out_last}")
    # Ширины столбцов задаёт второй header; первая таблица использует те же.

    # --- По дням
    sheet_title(days_ws, "План по дням", "Что делать в каждый день. В «Итог дня» — коротко, что получилось.")
    header(days_ws, HEADER_ROW, ["Дата", "День", "Этап", "Задачи на день", "Демо", "Итог дня"],
           [10, 6, 22, 80, 8, 40])
    for r, d in enumerate(DAYS, start=FIRST):
        stage = stage_of_day(d)
        lines = [f"#{t.id} {t.title} — {action}" for t, action in day_plan(mine, d)]
        values = [day(d), WEEKDAYS[day(d).weekday()], f"{stage.code} {stage.title}",
                  "\n".join(lines) or "—", "Да" if d == stage.demo else "", None]
        for col, value in enumerate(values, start=1):
            cell = body_cell(days_ws, r, col, value, "dd.mm" if col == 1 else None, wrap=col in (4, 6))
            if day(d).weekday() >= 5:
                cell.fill = WEEKEND_FILL
        days_ws.row_dimensions[r].height = max(18, 14 * max(1, len(lines)))
        mark_input(days_ws, "F", r, r)
    days_ws.conditional_formatting.add(
        f"A{FIRST}:F{FIRST + len(DAYS) - 1}",
        FormulaRule(formula=[f"$A{FIRST}=TODAY()"], font=Font(name=FONT, bold=True, color="C76A12")))
    days_ws.freeze_panes = f"A{FIRST}"

    # --- Гант
    gantt_sheet(gantt_ws, mine, src, id_rng, status_rng, f"$H${FIRST}:$H${last}", f"$I${FIRST}:$I${last}",
                color_by_owner=False, person_code=person.code)

    # --- Прогресс (только задачи, где я владелец)
    sheet_title(progress_ws, "Мой прогресс", "Считается по задачам, где ты владелец.")
    header(progress_ws, HEADER_ROW, ["Этап", "Задач", "Готово", "Готово, %", "Просрочено"], [26, 9, 9, 11, 11])
    role = f'{src}!$C${FIRST}:$C${last},"Владелец"'
    for r, s in enumerate(STAGES, start=FIRST):
        crit = f'{src}!$D${FIRST}:$D${last},"{s.code}",{role}'
        body_cell(progress_ws, r, 1, f"{s.code} {s.title} ({s.start}–{s.end}.11)")
        body_cell(progress_ws, r, 2, f"=COUNTIFS({crit})")
        body_cell(progress_ws, r, 3, f'=COUNTIFS({crit},{src}!{status_rng},"{DONE}")')
        body_cell(progress_ws, r, 4, f"=IF(B{r}=0,0,C{r}/B{r})", "0%")
        body_cell(progress_ws, r, 5, f'=COUNTIFS({crit},{src}!$L${FIRST}:$L${last},"Да")')
    p_last = FIRST + len(STAGES) - 1
    tot = p_last + 1
    body_cell(progress_ws, tot, 1, "Итого").font = font(bold=True)
    for col in "BCE":
        body_cell(progress_ws, tot, ord(col) - 64, f"=SUM({col}{FIRST}:{col}{p_last})").font = font(bold=True)
    body_cell(progress_ws, tot, 4, f"=IF(B{tot}=0,0,C{tot}/B{tot})", "0%").font = font(bold=True)
    percent_bar(progress_ws, f"D{FIRST}:D{tot}")

    help_sheet(help_ws, general=False)
    wb.calculation.fullCalcOnLoad = True
    return wb


def help_sheet(ws: Worksheet, general: bool) -> None:
    sheet_title(ws, "Как пользоваться", "Короткая инструкция и пример заполненной строки.")
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 90
    lines = [
        ("Что правится руками", "Только жёлтые ячейки: Статус, Факт готово, Комментарий (и «Итог дня» в личном)."),
        ("Статусы", "Не начато → В работе → На ревью (открыт PR) → Готово (влито в main и проверено на staging). "
                    "Заблокировано — ждёшь чужую задачу дольше плана. Отложено — сознательно выкинули."),
        ("Источник правды", "Личные файлы. Каждый отмечает только свои задачи (роль «Владелец»)."),
        ("Как обновить общий", "python tracker/build_trackers.py — на вечернем синке, после того как все "
                               "закоммитили свои личные файлы. Общий файл пересобирается целиком."),
        ("Если поменялся план", "Правим tracker/tracker_data.py → python tracker/build_trackers.py --personal. "
                                "Личные файлы пересоберутся, статусы и комментарии сохранятся."),
        ("Блокер", "Твоя задача ждёт чужую. Запас < 0 — чужая будет готова позже твоего старта: сразу "
                   "работай по плану Б и скажи на синке."),
        ("Пример строки", "ID 12 · Auth: login/logout/me… · Владелец · S1 · План 06.11–07.11 · "
                          "Статус «На ревью» · Факт готово пусто · Комментарий «PR #14, ждёт ревью B»"),
    ]
    if general:
        lines.insert(2, ("Этот файл", "Сводный: Дашборд, Этапы, Функционал, Блокеры, Гант считаются формулами "
                                      "из листа «Задачи». Статусы на нём перезаписываются из личных файлов."))
    for r, (k, v) in enumerate(lines, start=4):
        body_cell(ws, r, 1, k).font = font(bold=True)
        body_cell(ws, r, 2, v, wrap=True)


# ---------------------------------------------------------------- состояние


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def read_states(path: Path, sheet: str, status_col: int, fact_col: int, comment_col: int,
                role_col: int | None = None) -> dict[int, TaskState]:
    """Читает статусы из ранее собранного файла. Строки соучастника пропускаются:
    статус задачи ведёт её владелец."""
    if not path.exists():
        return {}
    wb = load_workbook(path, data_only=True)
    if sheet not in wb.sheetnames:
        return {}
    ws = wb[sheet]
    result = {}
    for row in ws.iter_rows(min_row=FIRST, values_only=True):
        task_id = row[0]
        if not isinstance(task_id, int) or task_id not in TASK_BY_ID:
            continue
        if role_col is not None and row[role_col - 1] != "Владелец":
            continue
        status = row[status_col - 1]
        if status not in STATUSES:
            print(f"  ! {path.name}: у задачи #{task_id} неизвестный статус {status!r}, ставлю «{STATUSES[0]}»")
            status = STATUSES[0]
        result[task_id] = TaskState(status, _as_date(row[fact_col - 1]), row[comment_col - 1])
    return result


def collect_states(folder: Path) -> dict[int, TaskState]:
    """Общий файл — запасной источник, личные перекрывают его по своим задачам."""
    states = read_states(folder / GENERAL_FILE, "Задачи", 13, 14, 17)
    for p in PEOPLE:
        personal = read_states(folder / p.file_name, "Мои_задачи", 10, 11, 17, role_col=3)
        states.update({tid: st for tid, st in personal.items() if TASK_BY_ID[tid].owner == p.code})
    return states


def save(wb: Workbook, path: Path) -> bool:
    try:
        wb.save(path)
    except PermissionError:
        print(f"  ✗ {path.name} открыт в Excel — закрой и запусти ещё раз")
        return False
    print(f"  ✓ {path.name}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--personal", action="store_true", help="пересобрать и личные файлы (статусы сохраняются)")
    parser.add_argument("--out", type=Path, default=HERE, help="папка с трекерами (по умолчанию рядом со скриптом)")
    args = parser.parse_args(argv)
    # Консоль Windows по умолчанию в cp1251 и падает на «✓»; в CI (Linux) это ничего не меняет.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args.out.mkdir(parents=True, exist_ok=True)
    states = collect_states(args.out)
    ok = True
    for p in PEOPLE:
        path = args.out / p.file_name
        if args.personal or not path.exists():
            ok &= save(build_personal(p, states), path)
    ok &= save(build_general(states), args.out / GENERAL_FILE)
    # Текстовый двойник общего трекера: тот же срез, читается на GitHub и в диффе.
    status_path = args.out / STATUS_FILE
    status_path.write_text(status_md(states, date.today()), encoding="utf-8")
    print(f"  ✓ {status_path.name}")
    done = sum(1 for st in states.values() if st.status == DONE)
    print(f"Готово задач: {done} из {len(TASKS)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
