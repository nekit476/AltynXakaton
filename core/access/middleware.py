from django.contrib.auth.middleware import LoginRequiredMiddleware
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse
from django.shortcuts import resolve_url

# 204: тела нет, а HTMX выполняет переход по заголовку HX-Redirect.
HTTP_NO_CONTENT = 204


class DekanatLoginRequiredMiddleware(LoginRequiredMiddleware):
    """Вход обязателен для всех адресов, кроме помеченных `@login_not_required`.

    Отличие от встроенного: на HTMX-запрос без входа отвечаем заголовком HX-Redirect.
    Обычный 302 HTMX выполнил бы сам и вставил страницу входа внутрь фрагмента.
    """

    def handle_no_permission(self, request, view_func):
        if getattr(request, "htmx", False):
            login_url = resolve_url(self.get_login_url(view_func))
            response = HttpResponse(status=HTTP_NO_CONTENT)
            response["HX-Redirect"] = redirect_to_login(request.get_full_path(), login_url).url
            return response
        return super().handle_no_permission(request, view_func)
