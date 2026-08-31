"""Cadastro de usuários operacionais (mecânicos)."""

import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.utils import normalize_phone

from .models import Role, User

MECHANIC_PIN_PATTERN = re.compile(r"^\d{4}$")


def split_display_name(name: str) -> tuple[str, str]:
    parts = (name or "").strip().split(None, 1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


@transaction.atomic
def create_mechanic_user(
    *,
    name: str,
    username: str,
    pin: str,
    phone: str = "",
    actor,
) -> User:
    """Cria mecânico ativo com PIN de 4 dígitos como senha de login."""
    if not actor.can_manage_users:
        raise PermissionDenied("Seu perfil não pode cadastrar mecânicos.")

    name = " ".join((name or "").split())
    username = (username or "").strip()
    pin = (pin or "").strip()
    phone = normalize_phone(phone) if phone else ""

    errors: dict[str, str] = {}
    if not name:
        errors["name"] = "Informe o nome do mecânico."
    if not username:
        errors["username"] = "Informe o usuário de login."
    elif User.objects.filter(username__iexact=username).exists():
        errors["username"] = "Este usuário já existe."
    if not MECHANIC_PIN_PATTERN.match(pin):
        errors["pin"] = "O PIN deve ter exatamente 4 dígitos."
    if errors:
        raise ValidationError(errors)

    first_name, last_name = split_display_name(name)
    user = User(
        username=username,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        role=Role.MECHANIC,
        is_active=True,
    )
    # PIN curto numérico — fluxo exclusivo de mecânico; não passa pelos validators padrão.
    user.set_password(pin)
    user.save()
    return user
