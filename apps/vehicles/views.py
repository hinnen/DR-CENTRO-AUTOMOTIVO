from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, UpdateView

from apps.core.permissions import RoleRequiredMixin
from apps.workorders.models import ServiceOrderPhoto, ServiceTask

from .forms import VehicleForm
from .models import Vehicle
from .services import vehicle_summary


class VehicleDetailView(LoginRequiredMixin, DetailView):
    """Histórico do veículo: tudo o que já aconteceu com aquela placa."""

    model = Vehicle
    template_name = "vehicles/detail.html"
    context_object_name = "vehicle"

    def get_object(self, queryset=None):
        return get_object_or_404(Vehicle.objects.select_related("client"), uuid=self.kwargs["uuid"])

    def get_context_data(self, **kwargs):
        from apps.workorders.models import TaskStatus

        context = super().get_context_data(**kwargs)
        vehicle = self.object

        context.update(vehicle_summary(vehicle))

        # Carrega serviços e fotos junto: cada atendimento da linha do tempo
        # mostra os dois, e sem prefetch seriam duas queries por OS.
        orders = list(
            vehicle.service_orders.with_related()
            .prefetch_related(
                Prefetch(
                    "tasks",
                    queryset=ServiceTask.objects.exclude(status=TaskStatus.CANCELLED).order_by(
                        "position", "id"
                    ),
                ),
                Prefetch(
                    "photos",
                    queryset=ServiceOrderPhoto.objects.visible().order_by("created_at", "id"),
                    to_attr="visible_photos",
                ),
            )
            .order_by("-entry_at")
        )

        context["orders"] = orders
        context["first_entry_at"] = orders[-1].entry_at if orders else None
        context["page_title"] = vehicle.plate_display
        return context


class VehicleUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/form.html"
    required_capability = "can_manage_customers"

    def get_object(self, queryset=None):
        return get_object_or_404(Vehicle.objects.select_related("client"), uuid=self.kwargs["uuid"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Editar {self.object.plate_display}"
        context["client"] = self.object.client
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Veículo atualizado.")
        return response
