"""Тесты данных плана и синхронизации трекеров."""

from __future__ import annotations

import sys
from pathlib import Path

import allure
import pytest
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_trackers as bt
from md_render import feature_label, person_md
from tracker_data import (
    DAYS_LIST,
    FEATURE_BY_CODE,
    PEOPLE_BY_CODE,
    STAGE_BY_CODE,
    TASK_BY_ID,
    TASKS,
    blockers,
    day_plan,
    risk_for_slack,
    tasks_of,
)


class TestPlanData:
    """Целостность плана.

    - test_references_exist: зависимости, этапы, фичи и владельцы существуют
    - test_task_dates: даты задачи внутри проекта, начало не позже конца
    - test_task_not_finishes_before_dependency: задача не кончается раньше своей зависимости
    """

    @allure.title("Все ссылки в задачах указывают на существующие сущности")
    def test_references_exist(self):
        for t in TASKS:
            assert t.stage in STAGE_BY_CODE, t
            assert t.feature in FEATURE_BY_CODE, t
            assert t.owner in PEOPLE_BY_CODE, t
            assert all(c in PEOPLE_BY_CODE and c != t.owner for c in t.co), t
            assert all(d in TASK_BY_ID and d != t.id for d in t.deps), t

    @allure.title("Даты задачи лежат в 4–22 ноября и начало не позже конца")
    def test_task_dates(self):
        bad = [t.id for t in TASKS if not (4 <= t.start <= t.end <= 22)]
        assert not bad, f"даты вне 4–22.11 или начало позже конца: {bad}"

    @allure.title("Задача не заканчивается раньше задачи, от которой зависит")
    def test_task_not_finishes_before_dependency(self):
        bad = [(t.id, d) for t in TASKS for d in t.deps if TASK_BY_ID[d].end > t.end]
        assert not bad


class TestBlockers:
    """Расчёт блокеров.

    - test_risk_for_slack: граница рисков по запасу дней
    - test_only_cross_owner: блокер — всегда чужая задача
    - test_known_blocker: экран предметов C ждёт сдачу ДЗ B, готовую позже старта
    """

    @allure.title("Риск по запасу: {slack} дн → {expected}")
    @pytest.mark.parametrize(
        ("slack", "expected"),
        [(-2, "Высокий"), (-1, "Высокий"), (0, "Средний"), (1, "Низкий"), (5, "Низкий")],
    )
    def test_risk_for_slack(self, slack, expected):
        assert risk_for_slack(slack) == expected

    @allure.title("Свои зависимости не считаются блокерами")
    def test_only_cross_owner(self):
        assert all(b.waiting.owner != b.blocking.owner for b in blockers())

    @allure.title("#34 (C) ждёт #30 (B): запас −2 дня, высокий риск, план Б — заглушки контракта")
    def test_known_blocker(self):
        b = next(b for b in blockers() if b.waiting.id == 34 and b.blocking.id == 30)
        # #30 готова в конце 10.11, а #34 стартует 9.11: 9 − 10 − 1 = −2.
        assert (b.slack_days, b.risk) == (-2, "Высокий")
        assert "заглушках сервисов" in b.plan_b and "#30" in b.plan_b


class TestMarkdownTwins:
    """Markdown-двойники.

    - test_day_plan_actions: формулировка действия по дню задачи
    - test_feature_label: состояние функции по её задачам (как формула Excel)
    - test_person_md_complete: в личном md есть все задачи человека и все 19 дней
    """

    @allure.title("Задача 06–07.11 в день {d}.11 → «{expected}»")
    @pytest.mark.parametrize(("d", "expected"), [(6, "начать"), (7, "закончить")])
    def test_day_plan_actions(self, d, expected):
        plan = dict((t.id, a) for t, a in day_plan([TASK_BY_ID[12]], d))
        assert plan == {12: expected}

    @allure.title("Однодневная задача — «сделать», вне дат — нет в плане")
    def test_day_plan_single_and_outside(self):
        assert [a for _, a in day_plan([TASK_BY_ID[1]], 4)] == ["сделать"]
        assert day_plan([TASK_BY_ID[1]], 5) == []

    @allure.title("Состояние функции: {total} задач, готово {done}, в работе {active} → {expected}")
    @pytest.mark.parametrize(
        ("total", "done", "active", "expected"),
        [(0, 0, 0, "—"), (3, 0, 0, "Не начато"), (3, 0, 1, "В работе"), (3, 1, 0, "В работе"), (3, 3, 0, "Готово")],
    )
    def test_feature_label(self, total, done, active, expected):
        assert feature_label(total, done, active) == expected

    @allure.title("plan_{code}.md содержит все задачи участника и план на все дни")
    @pytest.mark.parametrize("code", ["A", "B", "C"])
    def test_person_md_complete(self, code):
        text = person_md(PEOPLE_BY_CODE[code])
        missing = [t.id for t in tasks_of(code) if f"**#{t.id}**" not in text]
        assert not missing
        day_rows = [line for line in text.splitlines() if line.startswith("| ") and ".11 " in line[:12]]
        assert len(day_rows) == len(DAYS_LIST)


class TestSync:
    """Синхронизация статусов личные → общий.

    - test_owner_status_reaches_general: статус владельца попадает в общий
    - test_coowner_edit_ignored: правка соучастника в своём файле не перетирает владельца
    - test_personal_rebuild_keeps_status: пересборка личных сохраняет статусы
    """

    @staticmethod
    def _set_status(path: Path, task_id: int, status: str) -> None:
        wb = load_workbook(path)
        ws = wb["Мои_задачи"]
        row = next(r for r in range(bt.FIRST, ws.max_row + 1) if ws.cell(r, 1).value == task_id)
        ws.cell(row, 10).value = status
        wb.save(path)

    @staticmethod
    def _general_status(folder: Path, task_id: int) -> str:
        ws = load_workbook(folder / bt.GENERAL_FILE)["Задачи"]
        row = next(r for r in range(bt.FIRST, ws.max_row + 1) if ws.cell(r, 1).value == task_id)
        return ws.cell(row, 13).value

    @pytest.fixture
    def folder(self, tmp_path: Path) -> Path:
        assert bt.main(["--out", str(tmp_path)]) == 0
        return tmp_path

    @allure.title("Статус «Готово» из личного файла B попадает в общий Excel и в STATUS.md")
    def test_owner_status_reaches_general(self, folder: Path):
        self._set_status(folder / PEOPLE_BY_CODE["B"].file_name, 29, "Готово")
        assert bt.main(["--out", str(folder)]) == 0
        assert self._general_status(folder, 29) == "Готово"
        status = (folder / bt.STATUS_FILE).read_text(encoding="utf-8")
        assert "| Готово задач | 1 из 75 (1 %) |" in status

    @allure.title("Соучастник C отметил #28 у себя — в общем остаётся статус владельца A")
    def test_coowner_edit_ignored(self, folder: Path):
        self._set_status(folder / PEOPLE_BY_CODE["C"].file_name, 28, "Готово")
        assert bt.main(["--out", str(folder)]) == 0
        assert self._general_status(folder, 28) == "Не начато"

    @allure.title("--personal пересобирает личные файлы и сохраняет статусы")
    def test_personal_rebuild_keeps_status(self, folder: Path):
        path = folder / PEOPLE_BY_CODE["A"].file_name
        self._set_status(path, 12, "На ревью")
        assert bt.main(["--out", str(folder), "--personal"]) == 0
        states = bt.read_states(path, "Мои_задачи", 10, 11, 17, role_col=3)
        assert states[12].status == "На ревью"
