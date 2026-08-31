"""Operações de negócio das ordens de serviço.

As views não alteram status nem numeração diretamente: tudo passa por aqui,
dentro de ``transaction.atomic``. É o que garante que nunca sobre metade de uma
operação gravada e que toda mudança relevante deixe rastro em ``ActivityLog``.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import (
    BOARD_STATUSES,
    CLOSED_STATUSES,
    DEFAULT_INSPECTION_ITEMS,
    OPEN_STATUSES,
    ActivityLog,
    EventType,
    Inspection,
    InspectionItem,
    ItemCondition,
    OrderNumberCounter,
    PhotoCategory,
    ServiceOrder,
    ServiceOrderPhoto,
    ServiceOrderStatusHistory,
    ServiceTask,
    Status,
    TaskStatus,
)

# ---------------------------------------------------------------------------
# Auditoria
# ---------------------------------------------------------------------------


def log_activity(order: ServiceOrder, *, event_type: str, description: str, user, **metadata) -> ActivityLog:
    """Registra um evento na trilha de auditoria da OS.

    O ``metadata`` guarda apenas identificadores e rótulos já exibidos na
    interface — nunca credenciais, tokens ou dados pessoais além do que já
    consta na própria OS.
    """
    return ActivityLog.objects.create(
        service_order=order,
        actor=user if getattr(user, "is_authenticated", False) else None,
        event_type=event_type,
        description=description,
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# Numeração e abertura
# ---------------------------------------------------------------------------


def next_order_number() -> int:
    """Devolve o próximo número de OS.

    A linha do contador é travada até o fim da transação, então dois
    atendimentos simultâneos nunca recebem o mesmo número. Cancelar uma OS não
    libera o número: ele fica gasto para sempre.
    """
    counter, _ = OrderNumberCounter.objects.get_or_create(pk=1)
    counter = OrderNumberCounter.objects.select_for_update().get(pk=counter.pk)
    counter.current += 1
    counter.save(update_fields=["current"])
    return counter.current


@transaction.atomic
def create_service_order(
    *,
    client,
    vehicle,
    entry_km: int,
    customer_complaint: str,
    user,
    entry_at=None,
    mechanic=None,
    expected_delivery_at=None,
    location=None,
    priority=None,
    internal_notes: str = "",
) -> ServiceOrder:
    if not user.can_register_entry:
        raise PermissionDenied("Seu perfil não pode registrar entradas.")

    if entry_km is None or entry_km < 0:
        raise ValidationError({"entry_km": "Informe uma quilometragem válida."})

    if not str(customer_complaint or "").strip():
        raise ValidationError({"customer_complaint": "Descreva o motivo da entrada."})

    existing = (
        ServiceOrder.objects.select_for_update()
        .filter(vehicle_id=vehicle.pk, status__in=OPEN_STATUSES)
        .first()
    )
    if existing:
        raise ValidationError(
            f"Este veículo já tem {existing.number_display} aberta. "
            "Finalize ou cancele a OS atual antes de registrar nova entrada."
        )

    order = ServiceOrder(
        number=next_order_number(),
        client=client,
        vehicle=vehicle,
        entry_km=entry_km,
        entry_at=entry_at or timezone.now(),
        customer_complaint=customer_complaint.strip(),
        mechanic=mechanic,
        expected_delivery_at=expected_delivery_at,
        location=location,
        internal_notes=internal_notes,
        status=Status.WAITING_EVALUATION,
        created_by=user,
    )
    if priority:
        order.priority = priority
    order.full_clean(exclude=["number", "uuid"])
    order.save()

    ServiceOrderStatusHistory.objects.create(
        service_order=order,
        previous_status="",
        new_status=order.status,
        changed_by=user,
        note="Entrada registrada",
    )
    log_activity(
        order,
        event_type=EventType.ORDER_CREATED,
        description=f"Veículo recebido — {vehicle.plate}, {order.entry_km} km",
        user=user,
    )

    return order


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def validate_transition(order: ServiceOrder, new_status: str) -> None:
    if order.status in CLOSED_STATUSES:
        raise ValidationError(
            f"Esta OS está {order.get_status_display().lower()} e não pode mudar de status."
        )

    if new_status not in BOARD_STATUSES:
        # Entrega e cancelamento têm fluxo próprio, com dados obrigatórios.
        raise ValidationError(
            "Este status só pode ser aplicado pelo fluxo de saída ou de cancelamento."
        )


@transaction.atomic
def transition_service_order_status(
    order: ServiceOrder, *, new_status: str, user, note: str = ""
) -> ServiceOrder:
    if not user.can_change_status:
        raise PermissionDenied("Seu perfil não pode alterar o status.")

    # Relê com trava para não sobrescrever mudança feita em outro computador.
    locked = (
        ServiceOrder.objects.select_for_update()
        .select_related("client", "vehicle")
        .get(pk=order.pk)
    )

    if locked.status != new_status:
        validate_transition(locked, new_status)

        previous_status = locked.status
        locked.status = new_status

        if new_status == Status.FINISHED:
            locked.finished_at = timezone.now()
        elif previous_status == Status.FINISHED:
            locked.finished_at = None

        locked.save(update_fields=["status", "finished_at", "updated_at"])

        ServiceOrderStatusHistory.objects.create(
            service_order=locked,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=user,
            note=note,
        )
        log_activity(
            locked,
            event_type=(
                EventType.ORDER_FINISHED if new_status == Status.FINISHED else EventType.STATUS_CHANGED
            ),
            description=(
                "Serviço finalizado"
                if new_status == Status.FINISHED
                else f"{Status(previous_status).label} → {Status(new_status).label}"
            ),
            user=user,
            previous_status=previous_status,
            new_status=new_status,
        )
        from .status_whatsapp import attach_status_whatsapp_notify

        attach_status_whatsapp_notify(
            locked, previous_status=previous_status, new_status=new_status
        )

    # A instância recebida continua válida para quem chamou: sem isso, quem
    # guardou a referência anterior seguiria enxergando o status antigo.
    order.status = locked.status
    order.finished_at = locked.finished_at
    order.status_whatsapp_notify_url = getattr(locked, "status_whatsapp_notify_url", "")
    return order


@transaction.atomic
def finalize_service_order(order: ServiceOrder, *, user, note: str = "") -> ServiceOrder:
    """Marca o serviço como concluído — o carro continua na oficina."""
    return transition_service_order_status(order, new_status=Status.FINISHED, user=user, note=note)


# ---------------------------------------------------------------------------
# Campos da OS
# ---------------------------------------------------------------------------


@transaction.atomic
def update_diagnosis(order: ServiceOrder, *, diagnosis: str, user) -> ServiceOrder:
    if not user.can_update_diagnosis:
        raise PermissionDenied("Seu perfil não pode alterar o diagnóstico.")
    _assert_order_open(order)

    previous = order.diagnosis
    order.diagnosis = (diagnosis or "").strip()
    order.diagnosis_updated_at = timezone.now()
    order.diagnosis_updated_by = user
    order.save(
        update_fields=["diagnosis", "diagnosis_updated_at", "diagnosis_updated_by", "updated_at"]
    )

    if previous != order.diagnosis:
        log_activity(
            order,
            event_type=EventType.DIAGNOSIS_UPDATED,
            description="Diagnóstico atualizado",
            user=user,
        )
    return order


@transaction.atomic
def change_mechanic(order: ServiceOrder, *, mechanic, user) -> ServiceOrder:
    if not user.can_change_status:
        raise PermissionDenied("Seu perfil não pode alterar o mecânico.")
    _assert_order_open(order)

    order.mechanic = mechanic
    order.save(update_fields=["mechanic", "updated_at"])
    log_activity(
        order,
        event_type=EventType.MECHANIC_CHANGED,
        description=f"Mecânico: {mechanic.display_name if mechanic else 'não definido'}",
        user=user,
        mechanic_id=mechanic.pk if mechanic else None,
    )
    return order


@transaction.atomic
def change_location(order: ServiceOrder, *, location, user) -> ServiceOrder:
    if not user.can_change_status:
        raise PermissionDenied("Seu perfil não pode alterar a localização.")
    _assert_order_open(order)

    order.location = location
    order.save(update_fields=["location", "updated_at"])
    log_activity(
        order,
        event_type=EventType.LOCATION_CHANGED,
        description=f"Localização: {location.name if location else 'não definida'}",
        user=user,
        location_id=location.pk if location else None,
    )
    return order


@transaction.atomic
def change_expected_delivery(order: ServiceOrder, *, expected_delivery_at, user) -> ServiceOrder:
    if not user.can_change_status:
        raise PermissionDenied("Seu perfil não pode alterar a previsão.")
    _assert_order_open(order)

    order.expected_delivery_at = expected_delivery_at
    order.save(update_fields=["expected_delivery_at", "updated_at"])
    log_activity(
        order,
        event_type=EventType.DELIVERY_CHANGED,
        description=f"Previsão de entrega: {order.expected_delivery_display or 'não definida'}",
        user=user,
    )
    return order


# ---------------------------------------------------------------------------
# Serviços da OS
# ---------------------------------------------------------------------------


def _assert_order_open(order: ServiceOrder) -> None:
    if order.status in CLOSED_STATUSES:
        raise ValidationError(
            f"Esta OS está {order.get_status_display().lower()} e não aceita mais alterações."
        )


@transaction.atomic
def add_service_task(
    order: ServiceOrder, *, title: str, user, requested_description: str = "", mechanic=None
) -> ServiceTask:
    if not user.can_manage_tasks:
        raise PermissionDenied("Seu perfil não pode adicionar serviços.")
    _assert_order_open(order)

    title = " ".join(str(title or "").split())
    if not title:
        raise ValidationError({"title": "Informe o serviço."})

    last = order.tasks.aggregate(value=Max("position"))["value"]
    task = ServiceTask.objects.create(
        service_order=order,
        title=title,
        requested_description=(requested_description or "").strip(),
        mechanic=mechanic,
        position=(last or 0) + 1,
    )
    log_activity(
        order,
        event_type=EventType.TASK_ADDED,
        description=f'Serviço adicionado: "{task.title}"',
        user=user,
        task_id=task.pk,
    )
    return task


@transaction.atomic
def start_service_task(task: ServiceTask, *, user) -> ServiceTask:
    if not user.can_manage_tasks:
        raise PermissionDenied("Seu perfil não pode alterar serviços.")
    _assert_order_open(task.service_order)
    if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
        raise ValidationError("Só é possível iniciar um serviço pendente.")

    task.status = TaskStatus.RUNNING
    task.started_at = task.started_at or timezone.now()
    task.completed_at = None
    if task.mechanic is None and user.is_mechanic:
        task.mechanic = user
    task.save(update_fields=["status", "started_at", "completed_at", "mechanic", "updated_at"])

    log_activity(
        task.service_order,
        event_type=EventType.TASK_STARTED,
        description=f'Serviço iniciado: "{task.title}"',
        user=user,
        task_id=task.pk,
    )
    return task


@transaction.atomic
def complete_service_task(task: ServiceTask, *, user, performed_service: str = "") -> ServiceTask:
    if not user.can_manage_tasks:
        raise PermissionDenied("Seu perfil não pode concluir serviços.")
    _assert_order_open(task.service_order)
    if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
        raise ValidationError("Só é possível concluir um serviço pendente ou em execução.")

    task.status = TaskStatus.DONE
    task.started_at = task.started_at or timezone.now()
    task.completed_at = timezone.now()
    if performed_service:
        task.performed_service = performed_service.strip()
    # Quem conclui assume o serviço se ninguém tinha assumido: é o dado que
    # permitirá medir produtividade por mecânico mais adiante.
    if task.mechanic is None:
        task.mechanic = user
    task.save(
        update_fields=[
            "status",
            "started_at",
            "completed_at",
            "performed_service",
            "mechanic",
            "updated_at",
        ]
    )

    log_activity(
        task.service_order,
        event_type=EventType.TASK_COMPLETED,
        description=f'Serviço "{task.title}" concluído',
        user=user,
        task_id=task.pk,
    )
    return task


@transaction.atomic
def reopen_service_task(task: ServiceTask, *, user) -> ServiceTask:
    if not user.can_manage_tasks:
        raise PermissionDenied("Seu perfil não pode alterar serviços.")
    _assert_order_open(task.service_order)
    if task.status != TaskStatus.DONE:
        raise ValidationError("Só é possível reabrir um serviço concluído.")

    task.status = TaskStatus.PENDING
    task.completed_at = None
    task.save(update_fields=["status", "completed_at", "updated_at"])

    log_activity(
        task.service_order,
        event_type=EventType.TASK_REOPENED,
        description=f'Serviço "{task.title}" reaberto',
        user=user,
        task_id=task.pk,
    )
    return task


@transaction.atomic
def cancel_service_task(task: ServiceTask, *, user) -> ServiceTask:
    if not user.can_manage_tasks:
        raise PermissionDenied("Seu perfil não pode cancelar serviços.")
    _assert_order_open(task.service_order)
    if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
        raise ValidationError("Só é possível cancelar um serviço pendente ou em execução.")

    task.status = TaskStatus.CANCELLED
    task.completed_at = None
    task.save(update_fields=["status", "completed_at", "updated_at"])

    log_activity(
        task.service_order,
        event_type=EventType.TASK_CANCELLED,
        description=f'Serviço "{task.title}" cancelado',
        user=user,
        task_id=task.pk,
    )
    return task


# ---------------------------------------------------------------------------
# Fotos
# ---------------------------------------------------------------------------


@transaction.atomic
def add_photos(
    order: ServiceOrder,
    *,
    images,
    user,
    category: str,
    caption: str = "",
    angle: str = "",
) -> list:
    if not user.can_upload_photos:
        raise PermissionDenied("Seu perfil não pode enviar fotos.")
    _assert_order_open(order)

    if category not in PhotoCategory.values:
        raise ValidationError({"category": "Categoria de foto inválida."})

    from .models import PhotoAngle

    resolved_angle = (angle or PhotoAngle.EXTRA).strip() or PhotoAngle.EXTRA
    if resolved_angle not in PhotoAngle.values:
        raise ValidationError({"angle": "Ângulo de foto inválido."})

    # Ângulos guiados: uma foto ativa por posição — a anterior sai da galeria
    # (soft-delete) para não acumular 3 "frentes" na mesma OS. Troca de ângulo
    # ≠ exclusão da galeria: quem fotografa a vistoria precisa poder “Refazer”.
    if resolved_angle != PhotoAngle.EXTRA and category == PhotoCategory.INSPECTION:
        for previous in order.photos.visible().filter(angle=resolved_angle, category=category):
            previous.is_deleted = True
            previous.deleted_at = timezone.now()
            previous.deleted_by = user
            previous.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])
            log_activity(
                order,
                event_type=EventType.PHOTO_REMOVED,
                description=f"Foto de {previous.get_category_display().lower()} substituída",
                user=user,
                photo_id=previous.pk,
            )

    created = [
        ServiceOrderPhoto.objects.create(
            service_order=order,
            vehicle=order.vehicle,
            category=category,
            angle=resolved_angle,
            image=image,
            caption=(caption or "").strip(),
            uploaded_by=user,
        )
        for image in images
    ]

    if created:
        label = PhotoCategory(category).label.lower()
        quantity = len(created)
        angle_label = PhotoAngle(resolved_angle).label.lower()
        description = (
            f"{quantity} foto{'s' if quantity > 1 else ''} de {label} adicionada"
            f"{'s' if quantity > 1 else ''}"
        )
        if resolved_angle != PhotoAngle.EXTRA:
            description = f"Foto de vistoria ({angle_label}) adicionada"
        log_activity(
            order,
            event_type=EventType.PHOTOS_ADDED,
            description=description,
            user=user,
            category=category,
            angle=resolved_angle,
            quantity=quantity,
        )
    return created


@transaction.atomic
def remove_photo(photo: ServiceOrderPhoto, *, user) -> ServiceOrderPhoto:
    """Exclusão lógica: o arquivo permanece, o registro de quem apagou também."""
    if not user.can_delete_photos:
        raise PermissionDenied("Seu perfil não pode remover fotos.")
    _assert_order_open(photo.service_order)

    photo.is_deleted = True
    photo.deleted_at = timezone.now()
    photo.deleted_by = user
    photo.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])

    log_activity(
        photo.service_order,
        event_type=EventType.PHOTO_REMOVED,
        description=f"Foto de {photo.get_category_display().lower()} removida",
        user=user,
        photo_id=photo.pk,
    )
    return photo


# ---------------------------------------------------------------------------
# Vistoria
# ---------------------------------------------------------------------------


def get_or_build_inspection(order: ServiceOrder) -> Inspection:
    """Devolve a vistoria da OS, criando o checklist padrão na primeira vez."""
    inspection = getattr(order, "inspection", None)
    if inspection is not None:
        return inspection

    # Só cria checklist novo em OS aberta — OS fechada sem vistoria não inventa dados.
    _assert_order_open(order)

    from django.db import IntegrityError

    try:
        with transaction.atomic():
            inspection = Inspection.objects.create(service_order=order)
            InspectionItem.objects.bulk_create(
                [
                    InspectionItem(
                        inspection=inspection,
                        key=key,
                        label=label,
                        condition=ItemCondition.NOT_CHECKED,
                        position=position,
                    )
                    for position, (key, label) in enumerate(DEFAULT_INSPECTION_ITEMS, start=1)
                ]
            )
    except IntegrityError:
        # Corrida: outro request criou a vistoria no mesmo instante.
        inspection = Inspection.objects.filter(service_order=order).first()
        if inspection is None:
            raise
    return inspection


@transaction.atomic
def save_inspection(order: ServiceOrder, *, conditions: dict, notes_by_key: dict, fuel_level: str, notes: str, user) -> Inspection:
    if not user.can_perform_inspection:
        raise PermissionDenied("Seu perfil não pode registrar vistoria.")
    _assert_order_open(order)

    inspection = get_or_build_inspection(order)
    inspection.fuel_level = fuel_level
    inspection.notes = (notes or "").strip()
    inspection.performed_by = user
    inspection.performed_at = timezone.now()
    inspection.save(update_fields=["fuel_level", "notes", "performed_by", "performed_at", "updated_at"])

    for item in inspection.items.all():
        condition = conditions.get(item.key)
        if condition in ItemCondition.values:
            item.condition = condition
        item.note = (notes_by_key.get(item.key) or "").strip()[:200]
        item.save(update_fields=["condition", "note"])

    summary = inspection.summary
    log_activity(
        order,
        event_type=EventType.INSPECTION_SAVED,
        description=(
            f"Vistoria registrada — {summary['ok']} OK, "
            f"{summary['attention']} atenção, {summary['damage']} avaria"
        ),
        user=user,
        **summary,
    )
    return inspection


# ---------------------------------------------------------------------------
# Saída, entrega e cancelamento
# ---------------------------------------------------------------------------


@transaction.atomic
def deliver_vehicle(
    order: ServiceOrder,
    *,
    user,
    exit_km: int,
    delivered_at=None,
    exit_notes: str = "",
    exit_km_justification: str = "",
    received_by_name: str = "",
    received_by_document: str = "",
    signature=None,
) -> ServiceOrder:
    """Registra a saída do veículo e encerra a OS como entregue."""
    if not user.can_deliver_vehicle:
        raise PermissionDenied("Seu perfil não pode registrar a saída do veículo.")

    locked = (
        ServiceOrder.objects.select_for_update()
        .select_related("client", "vehicle")
        .get(pk=order.pk)
    )

    if locked.status in CLOSED_STATUSES:
        raise ValidationError(
            f"Esta OS já está {locked.get_status_display().lower()}."
        )

    if exit_km is None or exit_km < 0:
        raise ValidationError({"exit_km": "Informe uma quilometragem válida."})

    # KM menor que o de entrada acontece de verdade: erro de digitação na
    # chegada ou troca de painel. Em vez de bloquear, exigimos justificativa
    # para que o histórico explique a diferença.
    if exit_km < locked.entry_km and not str(exit_km_justification or "").strip():
        raise ValidationError(
            {
                "exit_km_justification": (
                    f"KM de saída ({exit_km}) é inferior ao de entrada ({locked.entry_km}). "
                    "Justifique para continuar."
                )
            }
        )

    previous_status = locked.status
    now = timezone.now()

    locked.status = Status.DELIVERED
    locked.exit_km = exit_km
    locked.exit_notes = (exit_notes or "").strip()
    locked.exit_km_justification = (
        (exit_km_justification or "").strip() if exit_km < locked.entry_km else ""
    )
    locked.delivered_at = delivered_at or now
    locked.delivered_by = user
    locked.finished_at = locked.finished_at or now
    locked.received_by_name = " ".join(str(received_by_name or "").split())
    locked.received_by_document = str(received_by_document or "").strip()

    update_fields = [
        "status",
        "exit_km",
        "exit_notes",
        "exit_km_justification",
        "delivered_at",
        "delivered_by",
        "finished_at",
        "received_by_name",
        "received_by_document",
        "updated_at",
    ]

    if signature is not None:
        # ``save=False`` grava o arquivo no storage e só preenche o campo; o
        # save do model abaixo persiste tudo dentro da mesma transação.
        locked.delivery_signature.save("assinatura.png", signature, save=False)
        update_fields.append("delivery_signature")

    locked.save(update_fields=update_fields)

    ServiceOrderStatusHistory.objects.create(
        service_order=locked,
        previous_status=previous_status,
        new_status=Status.DELIVERED,
        changed_by=user,
        note="Veículo entregue",
    )
    retrieved_by = locked.received_by_name or locked.client.name
    log_activity(
        locked,
        event_type=EventType.VEHICLE_DELIVERED,
        description=f"Veículo entregue a {retrieved_by} por {user.display_name} — {exit_km} km",
        user=user,
        exit_km=exit_km,
        previous_status=previous_status,
        received_by_name=locked.received_by_name,
        has_signature=bool(locked.delivery_signature),
    )
    from .status_whatsapp import attach_status_whatsapp_notify

    attach_status_whatsapp_notify(
        locked, previous_status=previous_status, new_status=Status.DELIVERED
    )

    for field in (
        "status",
        "exit_km",
        "exit_notes",
        "exit_km_justification",
        "delivered_at",
        "delivered_by",
        "finished_at",
        "received_by_name",
        "received_by_document",
        "delivery_signature",
    ):
        setattr(order, field, getattr(locked, field))
    order.status_whatsapp_notify_url = getattr(locked, "status_whatsapp_notify_url", "")
    return order


@transaction.atomic
def cancel_service_order(order: ServiceOrder, *, user, reason: str) -> ServiceOrder:
    if not user.can_cancel_order:
        raise PermissionDenied("Seu perfil não pode cancelar ordens de serviço.")

    reason = str(reason or "").strip()
    if not reason:
        raise ValidationError({"cancellation_reason": "Informe o motivo do cancelamento."})

    locked = ServiceOrder.objects.select_for_update().get(pk=order.pk)
    if locked.status in CLOSED_STATUSES:
        raise ValidationError(f"Esta OS já está {locked.get_status_display().lower()}.")

    previous_status = locked.status
    locked.status = Status.CANCELLED
    locked.cancellation_reason = reason
    locked.cancelled_at = timezone.now()
    locked.cancelled_by = user
    locked.save(
        update_fields=["status", "cancellation_reason", "cancelled_at", "cancelled_by", "updated_at"]
    )

    ServiceOrderStatusHistory.objects.create(
        service_order=locked,
        previous_status=previous_status,
        new_status=Status.CANCELLED,
        changed_by=user,
        note=reason,
    )
    log_activity(
        locked,
        event_type=EventType.ORDER_CANCELLED,
        description=f"OS cancelada: {reason}"[:255],
        user=user,
        previous_status=previous_status,
    )

    for field in ("status", "cancellation_reason", "cancelled_at", "cancelled_by"):
        setattr(order, field, getattr(locked, field))
    return order


def workshop_whatsapp_contacts(*, query: str = "", focus_uuid=None) -> list[dict]:
    """Contatos WhatsApp dos veículos na oficina (atalho wa.me, sem API).

    Se ``focus_uuid`` for a OS da página aberta, esse cliente vem primeiro.
    """
    queryset = ServiceOrder.objects.with_related().in_workshop().order_by("entry_at")
    term = (query or "").strip()
    if term:
        queryset = queryset.search(term)

    orders = list(queryset[:80])
    focus_order = None
    if focus_uuid:
        focus_order = next((order for order in orders if str(order.uuid) == str(focus_uuid)), None)
        if focus_order is None:
            focus_order = (
                ServiceOrder.objects.with_related()
                .in_workshop()
                .filter(uuid=focus_uuid)
                .first()
            )
            if focus_order is not None and term:
                # Com busca ativa, só promove o foco se ele também bater no termo.
                focused_match = list(
                    ServiceOrder.objects.with_related()
                    .in_workshop()
                    .filter(uuid=focus_uuid)
                    .search(term)[:1]
                )
                focus_order = focused_match[0] if focused_match else None

    def row(order: ServiceOrder, *, pinned: bool = False) -> dict:
        client = order.client
        return {
            "order": order,
            "client_name": client.name,
            "phone_display": client.whatsapp_display,
            "wa_url": client.whatsapp_url,
            "plate": order.vehicle.plate_display,
            "vehicle": order.vehicle.description,
            "number": order.number_display,
            "status": order.get_status_display(),
            "pinned": pinned,
            "has_whatsapp": bool(client.whatsapp_url),
        }

    contacts: list[dict] = []
    seen = set()
    if focus_order is not None:
        contacts.append(row(focus_order, pinned=True))
        seen.add(focus_order.pk)

    for order in orders:
        if order.pk in seen:
            continue
        contacts.append(row(order))
        seen.add(order.pk)

    return contacts
