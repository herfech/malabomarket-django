from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["-created_at"]
    list_display = ["email", "full_name", "role", "is_verified", "is_active", "created_at"]
    list_filter = ["role", "is_verified", "is_professional", "is_active"]
    search_fields = ["email", "full_name", "phone"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("full_name", "phone", "whatsapp_number", "avatar")}),
        ("Rol y estado", {"fields": ("role", "is_verified", "is_professional", "is_active", "is_staff")}),
        ("Permisos avanzados", {"fields": ("groups", "user_permissions", "is_superuser")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "role"),
        }),
    )
