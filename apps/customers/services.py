from apps.core.utils import normalize_phone

from .models import Client


def find_by_phone(phone: str):
    """Clientes com o mesmo telefone.

    Usado antes de criar cadastro novo: telefone repetido quase sempre é o
    mesmo cliente sendo cadastrado duas vezes.
    """
    digits = normalize_phone(phone)
    if not digits:
        return Client.objects.none()
    return Client.objects.filter(phone=digits, is_active=True)
