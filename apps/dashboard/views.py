from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView

from apps.accounts.models import Role
from apps.vehicles.models import VehicleLocation
from apps.workorders.filters import active_filters, apply_filters
from apps.workorders.forms import mechanic_queryset
from apps.workorders.models import BOARD_STATUSES, ServiceOrder, Status


def _summary_link(request, *, clear=(), **setters):
    """Monta URL de filtro preservando busca/mecânico/chips já ativos."""
    params = request.GET.copy()
    for key in clear:
        params.pop(key, None)
    for key, value in setters.items():
        if value is None or value == "":
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"


def build_board(request):
    """Monta o quadro inteiro com uma única consulta.

    Buscar tudo de uma vez e agrupar em memória evita dezenas de queries: o
    Kanban tem seis colunas e cada card mostra cliente, veículo, mecânico e
    localização.
    """
    queryset = ServiceOrder.objects.with_related().with_card_data().on_board()
    orders = list(apply_filters(queryset, request).order_by("entry_at"))

    columns = []
    for status in BOARD_STATUSES:
        column_orders = [order for order in orders if order.status == status]
        columns.append(
            {
                "status": status.value,
                "label": status.label,
                "slug": status.value.lower().replace("_", "-"),
                "orders": column_orders,
                "count": len(column_orders),
            }
        )

    now = timezone.now()
    late = [
        order
        for order in orders
        if order.expected_delivery_at and order.expected_delivery_at < now
    ]

    def count_status(*statuses):
        return sum(1 for order in orders if order.status in statuses)

    summary = [
        {
            "label": "Na oficina",
            "value": len(orders),
            "url": _summary_link(request, clear=("status", "late")),
        },
        {
            "label": "Aguardando avaliação",
            "value": count_status(Status.WAITING_EVALUATION),
            "url": _summary_link(
                request, clear=("late",), status=Status.WAITING_EVALUATION.value
            ),
        },
        {
            "label": "Em manutenção",
            "value": count_status(Status.IN_SERVICE),
            "url": _summary_link(request, clear=("late",), status=Status.IN_SERVICE.value),
        },
        {
            "label": "Aguardando peça",
            "value": count_status(Status.WAITING_PART),
            "url": _summary_link(request, clear=("late",), status=Status.WAITING_PART.value),
        },
        {
            "label": "Atrasados",
            "value": len(late),
            "url": _summary_link(request, clear=("status",), late="1"),
            "danger": True,
        },
        {
            "label": "Prontos para entrega",
            "value": count_status(Status.FINISHED),
            "url": _summary_link(request, clear=("late",), status=Status.FINISHED.value),
        },
    ]

    return {
        "columns": columns,
        "summary_cards": summary,
        "total_orders": len(orders),
        "filters": active_filters(request),
    }


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_board(self.request))
        context["page_title"] = "Dashboard"
        context["mechanics"] = mechanic_queryset()
        context["locations"] = VehicleLocation.objects.filter(is_active=True)
        context["board_statuses"] = BOARD_STATUSES
        context["is_mechanic"] = self.request.user.role == Role.MECHANIC
        return context


@login_required
def board_partial(request):
    """Quadro + resumo (OOB) para o HTMX atualizar sem recarregar a página."""
    return render(request, "dashboard/partials/_board_live.html", build_board(request))
