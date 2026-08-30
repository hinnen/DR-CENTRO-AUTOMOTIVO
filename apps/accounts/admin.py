from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import UserCreateForm, UserUpdateForm
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = UserCreateForm
    form = UserUpdateForm
    model = User

    list_display = ("username", "display_name", "role", "email", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "first_name", "last_name", "email", "phone")
    ordering = ("first_name", "username")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Dados pessoais", {"fields": ("first_name", "last_name", "email", "phone")}),
        ("Perfil e acesso", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "first_name", "last_name", "email", "phone", "role", "password1", "password2"),
            },
        ),
    )

    @admin.display(description="nome")
    def display_name(self, obj: User) -> str:
        return obj.display_name
