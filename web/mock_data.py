"""Заглушки данных для вёрстки экранов — вымышленные.

Временный модуль: пока модели и селекторы domain/ не готовы (задачи B #7, #17, #31, #32, #33),
экраны верстаются на этих словарях. Когда появится `domain.<app>.selectors`, view меняет вызов
на селектор, а сюда никто не ходит. Модуль удаляется целиком после подключения всех экранов.
"""

from typing import Any

DAYS = ("Понедельник", "Вторник", "Среда", "Четверг", "Пятница")

# (день, пара, время, предмет, тип, аудитория, преподаватель, статус)
SCHEDULE: list[dict[str, Any]] = [
    {
        "day": 0,
        "time": "09:00–10:30",
        "subject": "Оптимизация",
        "kind": "Лекция",
        "room": "Г-301",
        "teacher": "Преподавателев П. И.",
        "status": "",
    },
    {
        "day": 0,
        "time": "10:45–12:15",
        "subject": "Основы ТАУ",
        "kind": "Практика",
        "room": "Г-215",
        "teacher": "Иванова А. С.",
        "status": "",
    },
    {
        "day": 1,
        "time": "12:30–14:00",
        "subject": "Физика",
        "kind": "Лаба",
        "room": "Г-108",
        "teacher": "Сидоров В. Н.",
        "status": "перенесена",
    },
    {
        "day": 2,
        "time": "09:00–10:30",
        "subject": "Оптимизация",
        "kind": "Практика",
        "room": "Г-301",
        "teacher": "Преподавателев П. И.",
        "status": "",
    },
    {
        "day": 2,
        "time": "14:15–15:45",
        "subject": "Английский язык",
        "kind": "Практика",
        "room": "Г-412",
        "teacher": "Петрова Е. К.",
        "status": "",
    },
    {
        "day": 3,
        "time": "10:45–12:15",
        "subject": "Основы ТАУ",
        "kind": "Лекция",
        "room": "Г-215",
        "teacher": "Иванова А. С.",
        "status": "отменена",
    },
    {
        "day": 4,
        "time": "09:00–10:30",
        "subject": "Физика",
        "kind": "Лекция",
        "room": "Г-108",
        "teacher": "Сидоров В. Н.",
        "status": "",
    },
]

COURSES: list[dict[str, Any]] = [
    {
        "slug": "optimization",
        "title": "Оптимизация",
        "teacher": "Преподавателев П. И.",
        "progress": 70,
        "deadline": "ЛР 3 — до 12.11, 23:59",
        "sections": [
            {"title": "Литература", "items": ["Методичка по линейному программированию (PDF)"]},
            {
                "title": "ЛР 3. Симплекс-метод",
                "items": ["Задание (PDF)", "Загрузка отчёта — не сдано"],
            },
        ],
    },
    {
        "slug": "tau",
        "title": "Основы ТАУ",
        "teacher": "Иванова А. С.",
        "progress": 45,
        "deadline": "ДЗ 2 — до 15.11, 23:59",
        "sections": [{"title": "ДЗ 2", "items": ["Задание (PDF)", "Загрузка отчёта — не сдано"]}],
    },
    {
        "slug": "physics",
        "title": "Физика",
        "teacher": "Сидоров В. Н.",
        "progress": 90,
        "deadline": "",
        "sections": [{"title": "Лабы", "items": ["Лаба 4 — сдано, 5 баллов"]}],
    },
]

GRADES: list[dict[str, Any]] = [
    {
        "subject": "Оптимизация",
        "points": 58,
        "max": 100,
        "control": "Экзамен",
        "state": "debt",
        "note": "не хватает 3 баллов до допуска",
    },
    {
        "subject": "Основы ТАУ",
        "points": 74,
        "max": 100,
        "control": "Зачёт",
        "state": "ok",
        "note": "",
    },
    {
        "subject": "Физика",
        "points": 92,
        "max": 100,
        "control": "Экзамен",
        "state": "ok",
        "note": "автомат",
    },
    {
        "subject": "Английский язык",
        "points": 81,
        "max": 100,
        "control": "Зачёт",
        "state": "ok",
        "note": "",
    },
]

REQUESTS: list[dict[str, Any]] = [
    {
        "title": "Справка об обучении",
        "created": "28.10",
        "status": "Готова",
        "note": "Каб. 123, до 25.11",
    },
    {"title": "Справка в налоговую", "created": "03.11", "status": "В работе", "note": ""},
]

NOTIFICATIONS: list[dict[str, Any]] = [
    {"title": "Перенесена пара: Физика, лаба", "when": "сегодня, 09:12", "unread": True},
    {"title": "Новая оценка: Основы ТАУ, ДЗ 1 — 8 баллов", "when": "вчера", "unread": True},
    {"title": "Справка об обучении готова", "when": "30.10", "unread": False},
]

TODAY_DAY = 0  # «сегодня» в заглушке — понедельник


def get_course(slug: str) -> dict[str, Any] | None:
    return next((course for course in COURSES if course["slug"] == slug), None)
