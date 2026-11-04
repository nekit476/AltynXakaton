"""URL интерфейса. Разделы (расписание, учёба, заявки, /t/, /a/) добавляются сюда."""

from django.urls import path

from web import views

app_name = "web"

urlpatterns = [
    path("", views.home, name="home"),
]
