"""Filtros compartilhados pelo dashboard, Kanban e lista da oficina.

Ficam num só lugar para que os contadores do topo e o quadro não possam
divergir: os dois leem o mesmo filtro a partir da querystring.
"""

from django.utils import timezone

from .models import OPEN_STATUSES, Status


def apply_filters(queryset, request):
    params = request.GET

    term = params.get("q", "").strip()
    if term:
        queryset = queryset.search(term)

    status = params.get("status", "").strip()
    if status and status in Status.values:
        queryset = queryset.filter(status=status)

    mechanic = params.get("mechanic", "").strip()
    if mechanic == "none":
        queryset = queryset.filter(mechanic__isnull=True)
    elif mechanic:
        queryset = queryset.filter(mechanic__uuid=mechanic)

    location = params.get("location", "").strip()
    if location == "none":
        queryset = queryset.filter(location__isnull=True)
    elif location.isdigit():
        queryset = queryset.filter(location_id=int(location))

    if params.get("mine") == "1" and request.user.is_authenticated:
        queryset = queryset.filter(mechanic=request.user)

    if params.get("late") == "1":
        queryset = queryset.filter(
            status__in=OPEN_STATUSES,
            expected_delivery_at__isnull=False,
            expected_delivery_at__lt=timezone.now(),
        )

    if params.get("today") == "1":
        today = timezone.localdate()
        queryset = queryset.filter(expected_delivery_at__date=today)

    priority = params.get("priority", "").strip()
    if priority:
        queryset = queryset.filter(priority=priority)

    return queryset


def active_filters(request) -> dict:
    """Valores atuais, para repopular a barra de filtros e montar as URLs."""
    params = request.GET
    return {
        "q": params.get("q", ""),
        "status": params.get("status", ""),
        "mechanic": params.get("mechanic", ""),
        "location": params.get("location", ""),
        "mine": params.get("mine", ""),
        "late": params.get("late", ""),
        "today": params.get("today", ""),
        "priority": params.get("priority", ""),
        "has_any": any(
            params.get(key)
            for key in ("q", "status", "mechanic", "location", "mine", "late", "today", "priority")
        ),
    }
