from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Max

from .models import Vehicle, VehicleLocation, format_plate_display, normalize_plate

# Placa normalizada (antiga ou Mercosul) sempre tem 7 caracteres.
PLATE_LOOKUP_LENGTH = 7


def find_by_plate(plate: str) -> Vehicle | None:
    """Busca pela placa ignorando traço, espaço e pontuação.

    Compara sempre a forma normalizada (ABC1234 = ABC-1234). Se o banco tiver
    registro antigo sujo com hífen, ainda encontra.
    """
    normalized = normalize_plate(plate)
    if not normalized:
        return None

    qs = Vehicle.objects.select_related("client").filter(is_active=True)
    hit = qs.filter(plate=normalized).first()
    if hit:
        return hit

    # Fallback: cadastros antigos / import com hífen ou espaço no campo.
    for vehicle in qs.filter(plate__istartswith=normalized[:3]).iterator():
        if normalize_plate(vehicle.plate) == normalized:
            return vehicle
    return None


def vehicle_summary(vehicle: Vehicle) -> dict:
    """Resumo mostrado na busca por placa da Nova Entrada.

    Traz o que a recepção precisa para confirmar o carro em segundos: quantas
    vezes já passou, quando foi a última visita e com qual quilometragem.
    """
    stats = vehicle.service_orders.aggregate(
        visit_count=Count("pk"),
        last_entry_at=Max("entry_at"),
    )
    visit_count = stats["visit_count"] or 0
    last_order = None
    last_km = None

    if visit_count:
        last_order = (
            vehicle.service_orders.filter(entry_at=stats["last_entry_at"])
            .only("entry_at", "entry_km", "exit_km", "uuid", "number", "status")
            .first()
        )
        if last_order:
            last_km = last_order.exit_km or last_order.entry_km

    return {
        "vehicle": vehicle,
        "client": vehicle.client,
        "visit_count": visit_count,
        "last_order": last_order,
        "last_entry_at": stats["last_entry_at"],
        "last_km": last_km,
    }


def build_plate_lookup_context(*, plate: str, raw: str) -> dict:
    """Monta o contexto HTMX da busca por placa (desktop e mobile).

    Só consulta o banco com a placa completa (7 chars). Antes disso evita
    round-trips inúteis — no Render cada request soma latência de rede.
    """
    from apps.workorders.models import ServiceOrder

    context: dict = {
        "plate": plate,
        "raw": raw,
        "plate_display": format_plate_display(plate) if plate else "",
    }

    if len(plate) < PLATE_LOOKUP_LENGTH:
        if plate:
            context["typing"] = True
            context["remaining"] = PLATE_LOOKUP_LENGTH - len(plate)
        return context

    vehicle = find_by_plate(plate)
    if vehicle is None:
        context["not_found"] = True
        return context

    context["summary"] = vehicle_summary(vehicle)
    context["open_order"] = (
        ServiceOrder.objects.in_workshop()
        .filter(vehicle=vehicle)
        .order_by("-entry_at")
        .only("uuid", "number", "status", "entry_at")
        .first()
    )
    return context


@transaction.atomic
def create_location(*, name: str, actor) -> VehicleLocation:
    """Cadastro rápido de localização física do pátio."""
    if not actor.can_register_entry:
        raise PermissionDenied("Seu perfil não pode cadastrar localizações.")

    name = " ".join((name or "").split())
    if not name:
        raise ValidationError({"name": "Informe o nome da localização."})
    if VehicleLocation.objects.filter(name__iexact=name).exists():
        raise ValidationError({"name": "Já existe uma localização com este nome."})

    return VehicleLocation.objects.create(name=name, is_active=True)
