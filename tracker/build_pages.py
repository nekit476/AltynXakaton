"""Личные планы A, B, C (docs/plan/plan_<код>.html и .md) и бэклог (07_backlog.md).

Строятся из тех же данных, что и Excel-трекеры, поэтому сроки и блокеры в
плане, бэклоге и таблице не разъезжаются.

    python build_pages.py
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

from md_render import person_md
from people_notes import NOTES
from tracker_data import (
    DAYS_LIST,
    FEATURE_BY_CODE,
    PEOPLE,
    PEOPLE_BY_CODE,
    STAGES,
    TASKS,
    Person,
    blockers,
    day,
    day_plan,
    stage_of_day,
    tasks_of,
)

OUT = Path(__file__).resolve().parents[1] / "docs" / "plan"
WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
ACCENT = {"A": "--a", "B": "--b", "C": "--c"}

CSS = """
/* Layout: одна колонка ~1040px; разделы — листы с подписью слева, как в обзорном плане */
:root{
  --bg:#f3f5f4; --paper:#ffffff; --fg:#14211f; --muted:#5b6b68; --line:#d9e0de;
  --accent:#0e5c57; --accent-soft:#dcebe9; --flame:#c76a12; --flame-soft:#f6e6d4;
  --a:#0e5c57; --b:#6a4fb3; --c:#c76a12; --weekend:#e9eeec;
  --hi:#b3261e; --hi-soft:#fbe3e1; --mid:#8a5a00; --mid-soft:#fbefd2; --lo:#2f7d4a; --lo-soft:#e1f1e6;
  --f-display:"Unbounded","Onest",system-ui,sans-serif;
  --f-body:"Onest",system-ui,-apple-system,"Segoe UI",sans-serif;
  --f-mono:"JetBrains Mono",ui-monospace,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0f1716; --paper:#16201f; --fg:#e3ebe9; --muted:#93a4a0; --line:#2a3836;
  --accent:#5fc0b6; --accent-soft:#1c3533; --flame:#f0a050; --flame-soft:#3a2a18;
  --a:#5fc0b6; --b:#a991f0; --c:#f0a050; --weekend:#1b2726;
  --hi:#ff8a80; --hi-soft:#3d1f1d; --mid:#f0c060; --mid-soft:#3a3018; --lo:#6cc58a; --lo-soft:#1b3324;
  color-scheme:dark }}
:root[data-theme="dark"]{
  --bg:#0f1716; --paper:#16201f; --fg:#e3ebe9; --muted:#93a4a0; --line:#2a3836;
  --accent:#5fc0b6; --accent-soft:#1c3533; --flame:#f0a050; --flame-soft:#3a2a18;
  --a:#5fc0b6; --b:#a991f0; --c:#f0a050; --weekend:#1b2726;
  --hi:#ff8a80; --hi-soft:#3d1f1d; --mid:#f0c060; --mid-soft:#3a3018; --lo:#6cc58a; --lo-soft:#1b3324;
  color-scheme:dark }
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font-family:var(--f-body);font-size:15px;line-height:1.55;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));
  padding-block:32px 64px}
.wrap{max-width:1040px;margin:0 auto;display:flex;flex-direction:column;gap:28px}
h1,h2,h3{text-wrap:balance;margin:0}
h1{font-family:var(--f-display);font-weight:700;font-size:clamp(26px,4.6vw,40px);line-height:1.12}
h2{font-family:var(--f-display);font-weight:500;font-size:19px}
h3{font-size:15px;font-weight:600}
p{margin:0;max-width:68ch}
.muted{color:var(--muted)}
.label{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600}
header{display:flex;flex-direction:column;gap:12px}
.banner{align-self:flex-start;background:var(--flame-soft);color:var(--flame);font-weight:600;font-size:12px;
  padding:4px 10px;border-radius:999px}
.who-tag{font-family:var(--f-mono);color:var(--k);}
.facts{display:flex;flex-wrap:wrap;gap:8px 28px;margin-top:4px}
.facts div{display:flex;flex-direction:column}
.facts b{font-family:var(--f-mono);font-size:22px;font-weight:600;font-variant-numeric:tabular-nums}
section{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:24px;
  display:grid;grid-template-columns:180px 1fr;gap:20px}
section>.side{display:flex;flex-direction:column;gap:6px}
section>.body{min-width:0;display:flex;flex-direction:column;gap:16px}
@media (max-width:760px){section{grid-template-columns:1fr;padding:18px}}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.gantt{display:grid;grid-template-columns:minmax(220px,2.4fr) repeat(19,minmax(26px,1fr));
  min-width:780px;font-size:12px}
.gantt .d{text-align:center;padding:4px 0;color:var(--muted);border-bottom:1px solid var(--line);font-size:11px}
.gantt .d b{display:block;color:var(--fg);font-family:var(--f-mono);font-size:12px}
.gantt .we{background:var(--weekend)}
.gantt .lbl{padding:5px 8px 5px 0;border-bottom:1px solid var(--line);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}
.gantt .lbl span{font-family:var(--f-mono);color:var(--muted);margin-right:6px}
.gantt .cell{border-bottom:1px solid var(--line)}
.gantt .bar{align-self:center;height:16px;margin:0 2px;border-radius:5px;background:var(--k);z-index:1}
.gantt .bar.co{background:transparent;border:2px dashed var(--k)}
.gantt .stg{grid-column:1/-1;font-weight:600;font-size:12px;color:var(--accent);padding:10px 0 4px;
  border-bottom:1px solid var(--line)}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12px;color:var(--muted)}
.legend i{display:inline-block;width:14px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.stages{display:flex;flex-direction:column;gap:14px}
.stage{border:1px solid var(--line);border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:8px}
.stage-head{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:baseline}
.stage-head .dates{font-family:var(--f-mono);font-size:13px;color:var(--muted)}
.task{display:grid;grid-template-columns:44px 1fr auto;gap:4px 10px;padding:6px 0;border-top:1px solid var(--line);
  font-size:14px}
.task:first-of-type{border-top:0}
.task .id{font-family:var(--f-mono);color:var(--muted)}
.task .meta{font-family:var(--f-mono);font-size:12px;color:var(--muted);white-space:nowrap}
.task .sub{grid-column:2/-1;font-size:13px;color:var(--muted)}
.chip{display:inline-block;font-size:11px;font-weight:600;padding:1px 8px;border-radius:999px;margin-left:6px;
  vertical-align:1px}
.chip.hi{background:var(--hi-soft);color:var(--hi)} .chip.mid{background:var(--mid-soft);color:var(--mid)}
.chip.lo{background:var(--lo-soft);color:var(--lo)} .chip.co{background:var(--accent-soft);color:var(--accent)}
.chip.opt{background:var(--weekend);color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:600}
td.num{font-family:var(--f-mono);white-space:nowrap;font-variant-numeric:tabular-nums}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
@media (max-width:760px){.grid2{grid-template-columns:1fr}}
.box{border:1px solid var(--line);border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:8px}
.box ul,.box ol{margin:0;padding-left:20px;font-size:14px;display:flex;flex-direction:column;gap:4px}
.prompt{background:var(--bg);border-left:3px solid var(--k);border-radius:6px;padding:10px 12px;font-size:14px}
code{font-family:var(--f-mono);font-size:13px;background:var(--accent-soft);padding:1px 5px;border-radius:4px;
  word-break:break-word}
.empty{color:var(--muted);font-size:14px}
a{color:var(--accent)}
:focus-visible{outline:2px solid var(--flame);outline-offset:2px}
"""

HEAD = """<title>{title}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600;700&family=Unbounded:wght@500;700&family=JetBrains+Mono:wght@400;600&display=swap">
<style>{css}</style>
"""


def e(text: object) -> str:
    return escape(str(text))


def dm(d: int) -> str:
    return f"{d:02d}.11"


def risk_chip(risk: str) -> str:
    cls = {"Высокий": "hi", "Средний": "mid", "Низкий": "lo"}[risk]
    return f'<span class="chip {cls}">риск: {e(risk.lower())}</span>'


def section(label: str, title: str, side_text: str, body: str, anchor: str) -> str:
    side = f'<p class="muted">{e(side_text)}</p>' if side_text else ""
    return (f'<section aria-labelledby="h-{anchor}"><div class="side"><span class="label">{e(label)}</span>'
            f'<h2 id="h-{anchor}">{e(title)}</h2>{side}</div><div class="body">{body}</div></section>')


def gantt(person: Person) -> str:
    mine = tasks_of(person.code)
    cells = ['<div style="grid-row:1;grid-column:1"></div>']
    for i, d in enumerate(DAYS_LIST):
        we = " we" if day(d).weekday() >= 5 or d == 4 else ""
        cells.append(f'<div class="d{we}" style="grid-row:1;grid-column:{i + 2}"><b>{d}</b>'
                     f'{WEEKDAYS[day(d).weekday()]}</div>')
    row = 2
    for stage in STAGES:
        stage_tasks = [t for t in mine if t.stage == stage.code]
        if not stage_tasks:
            continue
        cells.append(f'<div class="stg" style="grid-row:{row}">{e(stage.code)} · {e(stage.title)} · '
                     f'{dm(stage.start)}–{dm(stage.end)}</div>')
        row += 1
        for t in stage_tasks:
            cells.append(f'<div class="lbl" style="grid-row:{row};grid-column:1" title="{e(t.title)}">'
                         f'<span>#{t.id}</span>{e(t.title)}</div>')
            for i, d in enumerate(DAYS_LIST):
                we = " we" if day(d).weekday() >= 5 or d == 4 else ""
                cells.append(f'<div class="cell{we}" style="grid-row:{row};grid-column:{i + 2}"></div>')
            first = DAYS_LIST.index(t.start) + 2
            last = DAYS_LIST.index(t.end) + 3
            co = "" if t.owner == person.code else " co"
            cells.append(f'<div class="bar{co}" style="grid-row:{row};grid-column:{first}/{last}" '
                         f'aria-label="#{t.id}: {dm(t.start)}–{dm(t.end)}"></div>')
            row += 1
    legend = ('<div class="legend"><span><i style="background:var(--k)"></i>я владелец</span>'
              '<span><i style="border:2px dashed var(--k)"></i>я участник</span>'
              '<span><i style="background:var(--weekend)"></i>выходные (4.11 — праздник)</span></div>')
    return f'<div class="scroll"><div class="gantt">{"".join(cells)}</div></div>{legend}'


def stages_block(person: Person) -> str:
    mine = tasks_of(person.code)
    incoming = {}
    for b in blockers():
        if b.waiting.owner == person.code:
            incoming.setdefault(b.waiting.id, []).append(b)
    parts = []
    for stage in STAGES:
        stage_tasks = [t for t in mine if t.stage == stage.code]
        rows = []
        for t in stage_tasks:
            chips = ""
            if t.owner != person.code:
                chips += f'<span class="chip co">помогаю {e(t.owner)}</span>'
            if t.pri == "C":
                chips += '<span class="chip opt">если успеем</span>'
            sub = ""
            if t.id in incoming:
                worst = min(incoming[t.id], key=lambda b: b.slack_days)
                waits = ", ".join(f"#{b.blocking.id} ({b.blocking.owner}, {dm(b.blocking.end)})"
                                  for b in incoming[t.id])
                chips += risk_chip(worst.risk)
                sub = f'<div class="sub">Жду {e(waits)}. План Б: {e(worst.plan_b)}</div>'
            feature = FEATURE_BY_CODE[t.feature].title
            span = dm(t.start) if t.start == t.end else f"{dm(t.start)}–{dm(t.end)}"
            rows.append(f'<div class="task"><span class="id">#{t.id}</span><div>{e(t.title)}{chips}'
                        f'<div class="muted" style="font-size:12px">{e(feature)}</div></div>'
                        f'<span class="meta">{span} · {e(t.size)}</span>{sub}</div>')
        body = "".join(rows) or '<p class="empty">В этом этапе своих задач нет.</p>'
        parts.append(f'<div class="stage"><div class="stage-head"><h3>{e(stage.code)} · {e(stage.title)}</h3>'
                     f'<span class="dates">{dm(stage.start)}–{dm(stage.end)} · демо {dm(stage.demo)}</span></div>'
                     f'<p class="muted" style="font-size:14px">{e(stage.goal)}</p>{body}</div>')
    return f'<div class="stages">{"".join(parts)}</div>'


def blockers_block(person: Person) -> str:
    all_b = blockers()
    incoming = [b for b in all_b if b.waiting.owner == person.code]
    outgoing = [b for b in all_b if b.blocking.owner == person.code]
    inc_rows = "".join(
        f"<tr><td class='num'>#{b.waiting.id}</td><td>{e(b.waiting.title)}<br><span class='muted'>начинаю "
        f"{dm(b.waiting.start)}</span></td><td class='num'>#{b.blocking.id} · {e(b.blocking.owner)}<br>"
        f"<span class='muted'>готово {dm(b.blocking.end)}</span></td><td>{risk_chip(b.risk)}</td>"
        f"<td>{e(b.plan_b)}</td></tr>" for b in incoming)
    out_rows = "".join(
        f"<tr><td class='num'>#{b.blocking.id}</td><td>{e(b.blocking.title)}<br><span class='muted'>мой срок "
        f"{dm(b.blocking.end)}</span></td><td class='num'>#{b.waiting.id} · {e(b.waiting.owner)}<br>"
        f"<span class='muted'>начинает {dm(b.waiting.start)}</span></td><td>{risk_chip(b.risk)}</td></tr>"
        for b in outgoing)
    inc = (f'<div class="scroll"><table><thead><tr><th>Моя</th><th>Задача</th><th>Жду</th><th>Риск</th>'
           f'<th>План Б, пока жду</th></tr></thead><tbody>{inc_rows}</tbody></table></div>'
           if incoming else '<p class="empty">Входящих блокеров нет.</p>')
    out = (f'<div class="scroll"><table><thead><tr><th>Моя</th><th>Задача</th><th>Кто ждёт</th><th>Риск</th>'
           f'</tr></thead><tbody>{out_rows}</tbody></table></div>'
           if outgoing else '<p class="empty">Никто не ждёт твоих задач.</p>')
    return (f"<h3>Я жду других</h3>{inc}<h3>Меня ждут</h3>"
            f'<p class="muted" style="font-size:14px">Сдвигаешь срок такой задачи — предупреди того, кто ждёт, '
            f"в тот же день, а не на синке.</p>{out}")


def days_block(person: Person) -> str:
    """План по дням — тот же, что на листе «По_дням» личного Excel."""
    mine = tasks_of(person.code)
    rows = []
    for d in DAYS_LIST:
        stage = stage_of_day(d)
        items = "".join(f"<li>#{t.id} {e(t.title)} <span class='muted'>— {e(action)}</span></li>"
                        for t, action in day_plan(mine, d))
        todo = f"<ul style='margin:0;padding-left:18px'>{items}</ul>" if items else "<span class='muted'>—</span>"
        demo = '<span class="chip co">демо</span>' if d == stage.demo else ""
        we = " style='background:var(--weekend)'" if day(d).weekday() >= 5 or d == 4 else ""
        rows.append(f"<tr{we}><td class='num'>{dm(d)} {WEEKDAYS[day(d).weekday()]}</td>"
                    f"<td class='num'>{e(stage.code)}{demo}</td><td>{todo}</td></tr>")
    return (f'<div class="scroll"><table><thead><tr><th>День</th><th>Этап</th><th>Что делать</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def build_page(person: Person) -> str:
    notes = NOTES[person.code]
    mine = tasks_of(person.code)
    owned = [t for t in mine if t.owner == person.code]
    all_b = blockers()
    hi_in = sum(1 for b in all_b if b.waiting.owner == person.code and b.risk == "Высокий")
    waits_me = len({b.waiting.id for b in all_b if b.blocking.owner == person.code})
    k = ACCENT[person.code]

    header = (f'<header style="--k:var({k})"><span class="banner">Концепт для конкурса «Цифровой деканат '
              f'будущего»</span><h1><span class="who-tag">{e(person.code)}</span> · {e(person.role)}</h1>'
              f'<p>{e(notes["mission"])}</p><p class="muted">{e(person.name)}. {e(notes["why"])}</p>'
              f'<div class="facts"><div><b>{len(owned)}</b><span class="label">мои задачи</span></div>'
              f'<div><b>{len(mine) - len(owned)}</b><span class="label">помогаю другим</span></div>'
              f'<div><b>{hi_in}</b><span class="label">блокеров с высоким риском</span></div>'
              f'<div><b>{waits_me}</b><span class="label">задач ждут меня</span></div></div></header>')

    zone = "".join(f"<li><code>{e(z)}</code></li>" for z in notes["zone"])
    reviews = "".join(f"<li>{e(r)}</li>" for r in notes["reviews"])
    zone_body = (f'<div class="grid2"><div class="box"><h3>Владею кодом</h3><ul>{zone}</ul></div>'
                 f'<div class="box"><h3>Ревьюю у других</h3><ul>{reviews}</ul></div></div>')

    tools = "".join(f"<li><b>{e(a)}</b> — {e(b)}</li>" for a, b in notes["claude"])
    prompts = "".join(f'<div class="prompt">{e(p)}</div>' for p in notes["prompts"])
    claude_body = (f'<div class="box"><h3>Что использую</h3><ul>{tools}</ul></div>'
                   f'<h3>Первые промпты</h3><p class="muted" style="font-size:14px">Это стартовые формулировки. '
                   f'Записывай в <code>docs/prompts.md</code>, как они звучали на самом деле, и что пришлось '
                   f'возвращать на доработку.</p>{prompts}')

    first = "".join(f"<li>{e(x)}</li>" for x in notes["first_day"])
    done = "".join(f"<li>{e(x)}</li>" for x in notes["done"])
    pdf = "".join(f"<li>{e(x)}</li>" for x in notes["pdf"])
    finish_body = (f'<div class="grid2"><div class="box"><h3>Первые два дня (4–5.11)</h3><ol>{first}</ol></div>'
                   f'<div class="box"><h3>Моя часть готова, когда</h3><ul>{done}</ul></div></div>'
                   f'<div class="box"><h3>Пишу в PDF для жюри</h3><ul>{pdf}</ul></div>')

    tracker = (f'<p>Статус отмечаешь в <code>tracker/{e(person.file_name)}</code>, в жёлтых ячейках листа '
               f'«Мои_задачи». На вечернем синке A запускает <code>python tracker/build_trackers.py</code>, и '
               f'общий трекер подтягивает твои статусы. Блокеры и план по дням лежат на соседних листах того же '
               f'файла.</p>')

    body = "".join([
        header,
        section("Когда", "Мой путь", "Плановые дни каждой задачи. Пунктир — задача другого участника, "
                "где я помогаю.", gantt(person), "path"),
        section("Что", "По этапам", "Размер: S — до 2 часов, M — до дня. «Если успеем» — опциональные задачи.",
                stages_block(person), "stages"),
        section("Зависимости", "Блокеры", "Рассчитаны заранее по зависимостям из бэклога. Запас < 0 значит, "
                "что чужая задача по плану будет готова позже моего старта.", blockers_block(person), "blk"),
        section("Каждый день", "По дням", "Начать, продолжить, закончить. Выходные выделены, 4.11 — праздник.",
                days_block(person), "days"),
        section("Где", "Моя зона", "", zone_body, "zone"),
        section("Как", "Работа с Claude", "", claude_body, "claude"),
        section("Итог", "Старт и финиш", "", finish_body, "finish"),
        section("Учёт", "Трекер", "", tracker, "tracker"),
    ])
    title = f"План {person.code}: {person.role}"
    return HEAD.format(title=e(title), css=CSS) + f'<div class="wrap" style="--k:var({k})">{body}</div>\n'


def build_backlog_md() -> str:
    """docs/plan/07_backlog.md — тот же список задач, что в трекерах, для чтения на GitHub."""
    lines = [
        "# 07. Бэклог",
        "",
        "Файл генерируется из `tracker/tracker_data.py` командой `python tracker/build_pages.py`. "
        "Руками не править: изменения потеряются при следующей сборке.",
        "",
        "Колонки: **Pri** — MoSCoW (M/S/C), **Size** — S ≤ 2 ч, M ≤ 1 дня, **Dep** — от каких задач зависит, "
        "**Ждёт** — зависимость от другого участника с риском. Каждая строка — issue в GitHub Projects.",
    ]
    risky = {}
    for b in blockers():
        risky.setdefault(b.waiting.id, []).append(f"#{b.blocking.id} {b.blocking.owner} ({b.risk.lower()})")
    for stage in STAGES:
        lines += ["", f"## {stage.code} «{stage.title}» ({dm(stage.start)}–{dm(stage.end)})", "",
                  f"Цель: {stage.goal[0].lower() + stage.goal[1:]}.", "",
                  "| ID | Задача | Owner | Pri | Size | Даты | Dep | Ждёт |", "|---|---|---|---|---|---|---|---|"]
        for t in (t for t in TASKS if t.stage == stage.code):
            owner = t.owner + ("".join(f" + {c}" for c in t.co))
            span = dm(t.start) if t.start == t.end else f"{dm(t.start)}–{dm(t.end)}"
            deps = ", ".join(str(d) for d in t.deps) or "—"
            lines.append(f"| {t.id} | {t.title} | {owner} | {t.pri} | {t.size} | {span} | {deps} | "
                         f"{'; '.join(risky.get(t.id, [])) or '—'} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    missing = set(PEOPLE_BY_CODE) - set(NOTES)
    if missing:
        print(f"  ✗ в people_notes.py нет текстов для: {', '.join(sorted(missing))}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for person in PEOPLE:
        path = OUT / f"plan_{person.code}.html"
        path.write_text(build_page(person), encoding="utf-8")
        print(f"  ✓ {path.name}")
        md_path = OUT / f"plan_{person.code}.md"
        md_path.write_text(person_md(person), encoding="utf-8")
        print(f"  ✓ {md_path.name}")
    backlog = OUT / "07_backlog.md"
    backlog.write_text(build_backlog_md(), encoding="utf-8")
    print(f"  ✓ {backlog.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
