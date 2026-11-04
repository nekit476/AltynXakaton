"""Views интерфейса: тонкие — права → данные → шаблон.

Данные пока из web/mock_data.py: после готовности domain/ (#7) берутся из селекторов.
"""

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from core.access import Perm, require_perm
from web import mock_data


@require_perm(Perm.VIEW_DASHBOARD)
def home(request: HttpRequest) -> HttpResponse:
    """«Сегодня»: пары дня, ближайшие дедлайны, свежие уведомления."""
    context = {
        "lessons": [x for x in mock_data.SCHEDULE if x["day"] == mock_data.TODAY_DAY],
        "deadlines": [c for c in mock_data.COURSES if c["deadline"]],
        "notifications": mock_data.NOTIFICATIONS[:2],
    }
    return render(request, "web/home.html", context)


@require_perm(Perm.VIEW_DASHBOARD)
def schedule(request: HttpRequest) -> HttpResponse:
    days = [
        {"name": name, "lessons": [x for x in mock_data.SCHEDULE if x["day"] == index]}
        for index, name in enumerate(mock_data.DAYS)
    ]
    return render(request, "web/schedule.html", {"days": days})


@require_perm(Perm.VIEW_DASHBOARD)
def notifications(request: HttpRequest) -> HttpResponse:
    return render(request, "web/notifications.html", {"items": mock_data.NOTIFICATIONS})


@require_perm(Perm.VIEW_OWN_STUDY)
def courses(request: HttpRequest) -> HttpResponse:
    return render(request, "web/courses.html", {"courses": mock_data.COURSES})


@require_perm(Perm.VIEW_OWN_STUDY)
def course_detail(request: HttpRequest, slug: str) -> HttpResponse:
    course = mock_data.get_course(slug)
    if course is None:
        raise Http404
    return render(request, "web/course_detail.html", {"course": course})


@require_perm(Perm.VIEW_OWN_STUDY)
def grades(request: HttpRequest) -> HttpResponse:
    debts = [g for g in mock_data.GRADES if g["state"] == "debt"]
    return render(request, "web/grades.html", {"grades": mock_data.GRADES, "debts": debts})


@require_perm(Perm.CREATE_REQUESTS)
def requests_list(request: HttpRequest) -> HttpResponse:
    return render(request, "web/requests.html", {"items": mock_data.REQUESTS})


@require_perm(Perm.MANAGE_OWN_COURSES)
def teacher_courses(request: HttpRequest) -> HttpResponse:
    return render(request, "web/teacher_courses.html", {"courses": mock_data.COURSES})


@require_perm(Perm.VIEW_STATISTICS)
def admin_overview(request: HttpRequest) -> HttpResponse:
    return render(request, "web/admin_overview.html")
