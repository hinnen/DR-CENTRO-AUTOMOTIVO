"""Cadastro e credenciais de usuários operacionais."""

import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.utils import normalize_phone

from .models import Role, User

OPERATIONAL_PIN_PATTERN = re.compile(r"^\d{4}$")
CREATABLE_ROLES = (Role.ADMIN, Role.RECEPTION, Role.MECHANIC)


def split_display_name(name: str) -> tuple[str, str]:
    parts = (name or "").strip().split(None, 1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def validate_operational_pin(pin: str) -> str | None:
    pin = (pin or "").strip()
    if not OPERATIONAL_PIN_PATTERN.match(pin):
        return "O PIN deve ter exatamente 4 dígitos."
    return None


def validate_new_username(username: str) -> str | None:
    username = (username or "").strip()
    if not username:
        return "Informe o usuário de login."
    if User.objects.filter(username__iexact=username).exists():
        return "Este usuário já existe."
    return None


@transaction.atomic
def create_operational_user(
    *,
    name: str,
    username: str,
    role: str,
    pin: str,
    phone: str = "",
    actor,
) -> User:
    """Cria usuário operacional (admin, recepção ou mecânico) com PIN de 4 dígitos."""
    if not actor.can_manage_users:
        raise PermissionDenied("Somente administradores cadastram usuários.")

    name = " ".join((name or "").split())
    username = (username or "").strip()
    pin = (pin or "").strip()
    phone = normalize_phone(phone) if phone else ""

    errors: dict[str, str] = {}
    if not name:
        errors["name"] = "Informe o nome."
    username_error = validate_new_username(username)
    if username_error:
        errors["username"] = username_error
    pin_error = validate_operational_pin(pin)
    if pin_error:
        errors["pin"] = pin_error
    if role not in CREATABLE_ROLES:
        errors["role"] = "Perfil inválido."
    if errors:
        raise ValidationError(errors)

    first_name, last_name = split_display_name(name)
    user = User(
        username=username,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        role=role,
        is_active=True,
        is_staff=role == Role.ADMIN,
    )
    user.set_password(pin)
    user.save()
    return user


@transaction.atomic
def set_user_pin(*, target: User, pin: str, actor) -> User:
    """Redefine o PIN de login de um usuário."""
    if not actor.can_manage_users:
        raise PermissionDenied("Somente administradores alteram PINs.")

    pin = (pin or "").strip()
    pin_error = validate_operational_pin(pin)
    if pin_error:
        raise ValidationError({"pin": pin_error})

    target.set_password(pin)
    target.save(update_fields=["password"])
    return target


@transaction.atomic
def create_mechanic_user(
    *,
    name: str,
    username: str,
    pin: str,
    phone: str = "",
    actor,
) -> User:
    """Cria mecânico ativo com PIN de 4 dígitos (cadastro rápido ou Configurações)."""
    if actor.can_manage_users:
        return create_operational_user(
            name=name,
            username=username,
            role=Role.MECHANIC,
            pin=pin,
            phone=phone,
            actor=actor,
        )

    if not actor.can_create_mechanic:
        raise PermissionDenied("Seu perfil não pode cadastrar mecânicos.")

    name = " ".join((name or "").split())
    username = (username or "").strip()
    pin = (pin or "").strip()
    phone = normalize_phone(phone) if phone else ""

    errors: dict[str, str] = {}
    if not name:
        errors["name"] = "Informe o nome do mecânico."
    username_error = validate_new_username(username)
    if username_error:
        errors["username"] = username_error
    pin_error = validate_operational_pin(pin)
    if pin_error:
        errors["pin"] = pin_error
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
    user.set_password(pin)
    user.save()
    return user
