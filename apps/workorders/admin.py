from django.contrib import admin

from .models import (
    ActivityLog,
    Inspection,
    InspectionItem,
    OrderNumberCounter,
    ServiceOrder,
    ServiceOrderPhoto,
    ServiceOrderStatusHistory,
    ServiceTask,
)


class StatusHistoryInline(admin.TabularInline):
    model = ServiceOrderStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("previous_status", "new_status", "changed_by", "changed_at", "note")

    def has_add_permission(self, request, obj=None):
        return False


class ServiceTaskInline(admin.TabularInline):
    model = ServiceTask
    extra = 0
    fields = ("position", "title", "status", "mechanic", "completed_at")
    ordering = ("position", "id")


class ActivityLogInline(admin.TabularInline):
    model = ActivityLog
    extra = 0
    can_delete = False
    readonly_fields = ("event_type", "description", "actor", "created_at", "metadata")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    list_display = (
        "number_display",
        "plate",
        "client",
        "status",
        "priority",
        "mechanic",
        "location",
        "entry_at",
        "expected_delivery_at",
    )
    list_filter = ("status", "priority", "mechanic", "location", "entry_at")
    search_fields = (
        "number",
        "vehicle__plate",
        "client__name",
        "client__phone",
        "vehicle__brand",
        "vehicle__model",
        "received_by_name",
    )
    autocomplete_fields = ("client", "vehicle")
    date_hierarchy = "entry_at"
    ordering = ("-entry_at",)
    inlines = [ServiceTaskInline, StatusHistoryInline, ActivityLogInline]
    readonly_fields = (
        "uuid",
        "number",
        "status",
        "created_by",
        "created_at",
        "updated_at",
        "finished_at",
        "delivered_at",
        "delivered_by",
        "cancelled_at",
        "cancelled_by",
        "diagnosis_updated_at",
        "diagnosis_updated_by",
    )

    @admin.display(description="OS", ordering="number")
    def number_display(self, obj: ServiceOrder) -> str:
        return obj.number_display

    @admin.display(description="placa", ordering="vehicle__plate")
    def plate(self, obj: ServiceOrder) -> str:
        return obj.vehicle.plate

    def has_delete_permission(self, request, obj=None):
        # OS não se apaga — só cancela pelo fluxo da oficina (regra de negócio).
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("client", "vehicle", "mechanic", "location")


@admin.register(ServiceOrderStatusHistory)
class ServiceOrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("service_order", "previous_status", "new_status", "changed_by", "changed_at")
    list_filter = ("new_status", "changed_at")
    search_fields = ("service_order__number", "service_order__vehicle__plate")
    ordering = ("-changed_at",)
    readonly_fields = ("service_order", "previous_status", "new_status", "changed_by", "changed_at", "note")

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("service_order", "changed_by")


@admin.register(ServiceTask)
class ServiceTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "service_order", "status", "mechanic", "completed_at")
    list_filter = ("status", "mechanic")
    search_fields = ("title", "service_order__number", "service_order__vehicle__plate")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("service_order", "mechanic")


@admin.register(ServiceOrderPhoto)
class ServiceOrderPhotoAdmin(admin.ModelAdmin):
    list_display = ("service_order", "category", "angle", "caption", "uploaded_by", "created_at", "is_deleted")
    list_filter = ("category", "angle", "is_deleted", "created_at")
    search_fields = ("service_order__number", "vehicle__plate", "caption")
    readonly_fields = ("uuid", "created_at", "updated_at", "deleted_at", "deleted_by")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("service_order", "vehicle", "uploaded_by")


class InspectionItemInline(admin.TabularInline):
    model = InspectionItem
    extra = 0
    fields = ("position", "label", "condition", "note")
    ordering = ("position", "id")


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ("service_order", "performed_by", "performed_at", "fuel_level")
    list_filter = ("fuel_level", "performed_at")
    search_fields = ("service_order__number", "service_order__vehicle__plate")
    inlines = [InspectionItemInline]
    ordering = ("-performed_at",)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Somente leitura: auditoria que pode ser editada não serve de auditoria."""

    list_display = ("created_at", "service_order", "event_type", "description", "actor")
    list_filter = ("event_type", "created_at")
    search_fields = ("service_order__number", "service_order__vehicle__plate", "description")
    readonly_fields = ("service_order", "actor", "event_type", "description", "metadata", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("service_order", "actor")


@admin.register(OrderNumberCounter)
class OrderNumberCounterAdmin(admin.ModelAdmin):
    list_display = ("__str__",)

    def has_add_permission(self, request):
        return OrderNumberCounter.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False
