"""Views интерфейса: тонкие — права → вызов сервиса из domain/ → шаблон."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from core.access import Perm, require_perm


@require_perm(Perm.VIEW_DASHBOARD)
def home(request: HttpRequest) -> HttpResponse:
    """Главная. Пока — витрина каркаса; станет экраном «Сегодня» (задача #57)."""
    return render(request, "web/home.html")
