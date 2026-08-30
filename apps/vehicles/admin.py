from django.contrib import admin

from .models import Vehicle, VehicleLocation


@admin.register(VehicleLocation)
class VehicleLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("order", "name")


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("plate", "brand", "model", "model_year", "color", "client", "is_active")
    list_filter = ("is_active", "fuel", "brand")
    search_fields = ("plate", "brand", "model", "chassis", "client__name", "client__phone")
    autocomplete_fields = ("client",)
    ordering = ("plate",)
    readonly_fields = ("uuid", "created_at", "updated_at")
