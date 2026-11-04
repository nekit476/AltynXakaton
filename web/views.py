"""Views интерфейса: тонкие — права → вызов сервиса из domain/ → шаблон."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def home(request: HttpRequest) -> HttpResponse:
    """Главная. Пока — витрина каркаса; станет экраном «Сегодня» (задача #57).

    Декоратора прав нет намеренно: после #13 (LoginRequiredMiddleware) главная
    сама станет доступна только после входа.
    """
    return render(request, "web/home.html")
