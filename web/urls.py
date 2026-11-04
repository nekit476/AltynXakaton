"""URL интерфейса. Новые разделы добавляются сюда; у каждого URL есть имя (для матрицы прав)."""

from django.urls import path

from web import views

app_name = "web"

urlpatterns = [
    path("", views.home, name="home"),
    path("schedule/", views.schedule, name="schedule"),
    path("notifications/", views.notifications, name="notifications"),
    path("courses/", views.courses, name="courses"),
    path("courses/<slug:slug>/", views.course_detail, name="course_detail"),
    path("grades/", views.grades, name="grades"),
    path("requests/", views.requests_list, name="requests"),
    path("t/courses/", views.teacher_courses, name="teacher_courses"),
    path("a/", views.admin_overview, name="admin_overview"),
]
