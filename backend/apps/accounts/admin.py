from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Staff support view of accounts. Product flows (claims, admissions) never happen here."""

    ordering = ("-created_at",)
    list_display = ("email", "name", "phone", "role", "is_offline", "is_active", "created_at")
    list_filter = ("role", "is_offline", "is_active", "is_staff")
    search_fields = ("email", "name", "phone")
    readonly_fields = ("id", "created_at", "updated_at", "last_login", "claimed_at")
    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        ("Profile", {"fields": ("name", "phone", "role", "domain")}),
        ("Status", {"fields": ("is_active", "is_offline", "claimed_at")}),
        ("Staff", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "name", "phone", "role", "password1", "password2")}),
    )
