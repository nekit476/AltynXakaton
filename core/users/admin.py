from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from core.users.models import User


@admin.register(User)
class DekanatUserAdmin(UserAdmin):
    list_display = ("username", "last_name", "first_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    fieldsets = (
        *UserAdmin.fieldsets,
        ("Дополнительно", {"fields": ("patronymic", "role")}),
    )
    add_fieldsets = (
        *UserAdmin.add_fieldsets,
        ("Дополнительно", {"fields": ("last_name", "first_name", "patronymic", "role")}),
    )
