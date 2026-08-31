"""Notificação de status ao cliente via wa.me (sem API WhatsApp)."""

from django.conf import settings

from apps.core.services.settings import auto_whatsapp_status_notify
from apps.core.utils import whatsapp_url

from .models import Status


def build_status_whatsapp_message(order, *, status_label: str) -> str:
    """Texto padrão enviado ao cliente quando o status da OS muda."""
    workshop = settings.WORKSHOP_NAME
    plate = order.vehicle.plate_display
    first_name = (order.client.name or "cliente").split()[0]
    return (
        f"Olá, {first_name}! Aqui é a {workshop}.\n"
        f"Atualização do veículo {plate} (OS {order.number_display}):\n"
        f"Status: {status_label}"
    )


def status_whatsapp_notify_url(
    order,
    *,
    previous_status: str,
    new_status: str,
) -> str:
    """URL wa.me com mensagem pronta, ou vazio se não aplicável."""
    if previous_status == new_status:
        return ""
    if not auto_whatsapp_status_notify():
        return ""
    if new_status == Status.CANCELLED:
        return ""

    phone = order.client.phone_whatsapp or order.client.phone
    if not phone:
        return ""

    try:
        label = Status(new_status).label
    except ValueError:
        label = new_status

    message = build_status_whatsapp_message(order, status_label=label)
    return whatsapp_url(phone, text=message)


def attach_status_whatsapp_notify(order, *, previous_status: str, new_status: str) -> None:
    """Grava URL de notificação na instância (consumida pelas views/JS)."""
    order.status_whatsapp_notify_url = status_whatsapp_notify_url(
        order,
        previous_status=previous_status,
        new_status=new_status,
    )
