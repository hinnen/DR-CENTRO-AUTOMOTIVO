"""Remove todos os registros marcados como demonstração."""

from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.customers.models import Client
from apps.vehicles.models import Vehicle, VehicleLocation
from apps.workorders.models import ServiceOrder


@transaction.atomic
def purge_demo_data(*, actor, password: str) -> dict[str, int]:
    """Exige a senha do administrador logado."""
    if not actor.can_manage_users:
        raise ValidationError("Somente administradores podem limpar exemplos.")
    if not authenticate(username=actor.username, password=password):
        raise ValidationError({"password": "Senha incorreta."})

    counts = {}
    counts["orders"] = ServiceOrder.objects.filter(is_demo=True).delete()[0]
    counts["vehicles"] = Vehicle.objects.filter(is_demo=True).delete()[0]
    counts["clients"] = Client.objects.filter(is_demo=True).delete()[0]
    counts["users"] = (
        User.objects.filter(is_demo=True).exclude(pk=actor.pk).delete()[0]
    )
    counts["locations"] = VehicleLocation.objects.filter(is_demo=True).delete()[0]
    return counts
