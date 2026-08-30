from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "phone_display", "email", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "phone", "phone_whatsapp", "email", "cpf_cnpj")
    ordering = ("name",)
    readonly_fields = ("uuid", "created_at", "updated_at")

    @admin.display(description="telefone")
    def phone_display(self, obj: Client) -> str:
        return obj.phone_display
