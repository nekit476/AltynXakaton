from django.contrib.auth import views as auth_views
from django.urls import path

app_name = "accounts"

urlpatterns = [
    # LoginView в Django 5.1+ уже помечен login_not_required.
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    # Выход — только POST (Django 5): выйти по ссылке из чужого письма нельзя.
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
