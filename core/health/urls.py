from django.urls import path

from core.health import views

app_name = "health"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("ready/", views.ready, name="ready"),
]
