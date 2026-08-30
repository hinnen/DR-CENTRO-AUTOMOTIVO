from .models import Vehicle, normalize_plate


def find_by_plate(plate: str) -> Vehicle | None:
    """Busca exata pela placa normalizada."""
    normalized = normalize_plate(plate)
    if not normalized:
        return None
    return (
        Vehicle.objects.select_related("client")
        .filter(plate=normalized, is_active=True)
        .first()
    )


def vehicle_summary(vehicle: Vehicle) -> dict:
    """Resumo mostrado na busca por placa da Nova Entrada.

    Traz o que a recepção precisa para confirmar o carro em segundos: quantas
    vezes já passou, quando foi a última visita e com qual quilometragem.
    """
    orders = vehicle.service_orders.order_by("-entry_at")
    last_order = orders.first()

    last_km = None
    if last_order:
        # O KM de saída é mais recente que o de entrada, quando existir.
        last_km = last_order.exit_km or last_order.entry_km

    return {
        "vehicle": vehicle,
        "client": vehicle.client,
        "visit_count": orders.count(),
        "last_order": last_order,
        "last_entry_at": last_order.entry_at if last_order else None,
        "last_km": last_km,
    }
