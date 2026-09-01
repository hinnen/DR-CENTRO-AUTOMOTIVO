from django.contrib import admin

from .models import BugReport, WorkshopSettings


@admin.register(WorkshopSettings)
class WorkshopSettingsAdmin(admin.ModelAdmin):
    list_display = ("reception_can_create_mechanic", "updated_at")

    def has_add_permission(self, request):
        return not WorkshopSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BugReport)
class BugReportAdmin(admin.ModelAdmin):
    list_display = ("pk", "usuario_nome", "app_context", "status", "created_at")
    list_filter = ("status", "app_context")
    search_fields = ("usuario_nome", "o_que_aconteceu", "url_pagina")
    readonly_fields = ("created_at", "print_base64", "print_mime")
    ordering = ("-created_at",)
