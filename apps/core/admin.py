from django.contrib import admin

from .models import WorkshopSettings


@admin.register(WorkshopSettings)
class WorkshopSettingsAdmin(admin.ModelAdmin):
    list_display = ("reception_can_create_mechanic", "updated_at")

    def has_add_permission(self, request):
        return not WorkshopSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
