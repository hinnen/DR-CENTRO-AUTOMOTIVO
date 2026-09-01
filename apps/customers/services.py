from django.db.models import Count, Q

from apps.core.utils import normalize_phone

from .models import Client


def find_by_phone(phone: str):
    """Clientes com o mesmo telefone (principal ou WhatsApp)."""
    digits = normalize_phone(phone)
    if not digits:
        return Client.objects.none()
    return Client.objects.filter(is_active=True).filter(
        Q(phone=digits) | Q(phone_whatsapp=digits)
    )


def search_clients(term: str, *, limit: int = 8):
    """Busca rápida por nome ou telefone — entrada de veículo novo."""
    term = (term or "").strip()
    if len(term) < 2:
        return Client.objects.none()
    return (
        Client.objects.active()
        .search(term)
        .annotate(vehicle_count=Count("vehicles"))
        .order_by("name")[:limit]
    )
