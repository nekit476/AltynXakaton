# Трекер «Зачётки»

| Файл | Кто правит |
|---|---|
| `Трекер_A_Никита.xlsx`, `Трекер_B.xlsx`, `Трекер_C.xlsx` | Каждый свой: статус, факт готовности, комментарий (жёлтые ячейки) |
| `Трекер_общий.xlsx` | Никто руками, пересобирается из личных |
| `STATUS.md` | Никто руками. Текстовый двойник общего трекера на дату сборки: сводка, этапы, люди, функционал, открытые блокеры, просрочки, все задачи, Гант |
| `tracker_data.py` | Сроки, владельцы, зависимости. После правки запусти `--personal` и `build_pages.py` |
| `people_notes.py` | Тексты личных планов |
| `md_render.py` | Сборка .md-двойников. Правила статусов те же, что в формулах Excel |

```bash
python build_trackers.py              # общий Excel + STATUS.md из личных (вечерний синк)
python build_trackers.py --personal   # пересобрать и личные после правки плана, статусы сохраняются
python build_pages.py                 # docs/plan: plan_A|B|C.html и .md, 07_backlog.md
```

Соответствие версий:

| Для людей | Markdown |
|---|---|
| `Трекер_общий.xlsx` | `tracker/STATUS.md` |
| `Трекер_<X>.xlsx` (задачи, блокеры, по дням) | `docs/plan/plan_<X>.md` (план) + раздел людей в `STATUS.md` (статусы) |
| `docs/plan/plan_<X>.html` | `docs/plan/plan_<X>.md` |
| `docs/plan/overview.html` | `docs/plan/00_overview.md` (вручную) |

Нужен только `openpyxl`. Тесты: `pytest tests`, линтер: `ruff check .`.
