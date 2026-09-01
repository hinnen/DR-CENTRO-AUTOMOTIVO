from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Max
from django.shortcuts import render
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.mixins import QueryStringMixin
from apps.core.permissions import RoleRequiredMixin

from .forms import ClientForm
from .models import Client
from .services import find_by_phone, search_clients


class ClientListView(LoginRequiredMixin, QueryStringMixin, ListView):
    model = Client
    template_name = "customers/list.html"
    context_object_name = "clients"
    paginate_by = 25

    def get_queryset(self):
        term = self.request.GET.get("q", "")
        return (
            Client.objects.active()
            .search(term)
            .annotate(order_count=Count("service_orders"), last_visit=Max("service_orders__entry_at"))
            .order_by("name")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Clientes"
        context["search_term"] = self.request.GET.get("q", "")
        return context


class ClientDetailView(LoginRequiredMixin, DetailView):
    model = Client
    template_name = "customers/detail.html"
    context_object_name = "client"

    def get_object(self, queryset=None):
        return Client.objects.prefetch_related("vehicles").get(uuid=self.kwargs["uuid"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client = self.object
        context["orders"] = client.service_orders.with_related().order_by("-entry_at")[:20]
        context["order_count"] = client.service_orders.count()
        context["last_visit"] = client.service_orders.aggregate(last=Max("entry_at"))["last"]
        context["page_title"] = client.name
        return context


class ClientCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = "customers/form.html"
    required_capability = "can_manage_customers"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Novo cliente"
        context["is_create"] = True
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Cliente {self.object.name} cadastrado.")
        return response


class ClientUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = "customers/form.html"
    required_capability = "can_manage_customers"

    def get_object(self, queryset=None):
        return Client.objects.get(uuid=self.kwargs["uuid"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Editar {self.object.name}"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Cliente atualizado.")
        return response


@login_required
def phone_lookup(request):
    """Aviso de possível duplicidade enquanto o telefone é digitado (HTMX)."""
    phone = request.GET.get("phone", "")
    clients = find_by_phone(phone) if phone else Client.objects.none()
    return render(
        request,
        "customers/partials/_phone_lookup.html",
        {"clients": clients, "phone": phone, "plate": request.GET.get("plate", "")},
    )


@login_required
def client_lookup(request):
    """Busca cliente por nome ou telefone — vincular veículo novo (HTMX)."""
    term = request.GET.get("q", "")
    pick_mode = request.GET.get("mode", "desktop")
    if pick_mode not in {"desktop", "mobile"}:
        pick_mode = "desktop"
    clients = search_clients(term)
    return render(
        request,
        "customers/partials/_client_lookup.html",
        {
            "clients": clients,
            "term": term.strip(),
            "plate": request.GET.get("plate", ""),
            "pick_mode": pick_mode,
        },
    )
