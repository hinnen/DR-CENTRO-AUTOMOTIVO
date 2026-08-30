from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from apps.accounts.models import Role, User
from apps.core.mixins import QueryStringMixin
from apps.customers.forms import ClientForm
from apps.customers.models import Client
from apps.vehicles.forms import VehicleForm
from apps.vehicles.models import VehicleLocation, normalize_plate
from apps.vehicles.services import find_by_plate, vehicle_summary

from .filters import active_filters, apply_filters
from .forms import (
    CancelOrderForm,
    CompleteTaskForm,
    DeliveryForm,
    DiagnosisForm,
    ExpectedDeliveryForm,
    InspectionForm,
    LocationChangeForm,
    MechanicChangeForm,
    PhotoUploadForm,
    ServiceOrderEntryForm,
    ServiceTaskForm,
    StatusChangeForm,
    mechanic_queryset,
)
from .models import (
    BOARD_STATUSES,
    PhotoCategory,
    ServiceOrder,
    ServiceOrderPhoto,
    ServiceTask,
    Status,
    TaskStatus,
)
from .services import (
    add_photos,
    add_service_task,
    cancel_service_order,
    cancel_service_task,
    change_expected_delivery,
    change_location,
    change_mechanic,
    complete_service_task,
    create_service_order,
    deliver_vehicle,
    finalize_service_order,
    get_or_build_inspection,
    remove_photo,
    reopen_service_task,
    save_inspection,
    start_service_task,
    transition_service_order_status,
    update_diagnosis,
)


# --------------------------------------------------------------------------
# Nova entrada
# --------------------------------------------------------------------------


@login_required
def plate_lookup(request):
    """Busca por placa da Nova Entrada (HTMX, dispara a cada tecla)."""
    raw = request.GET.get("plate", "")
    plate = normalize_plate(raw)

    context = {"plate": plate, "raw": raw}

    if len(plate) >= 3:
        vehicle = find_by_plate(plate)
        if vehicle:
            context["summary"] = vehicle_summary(vehicle)
            context["open_order"] = (
                ServiceOrder.objects.with_related()
                .in_workshop()
                .filter(vehicle=vehicle)
                .order_by("-entry_at")
                .first()
            )
        else:
            context["not_found"] = True

    return render(request, "workorders/partials/_plate_lookup.html", context)


@login_required
def new_entry(request):
    """Fluxo de entrada: identifica o veículo e abre a OS na mesma tela."""
    if not request.user.can_register_entry:
        raise PermissionDenied("Seu perfil não pode registrar entradas.")

    vehicle_uuid = request.GET.get("vehicle") or request.POST.get("vehicle")
    vehicle = None
    if vehicle_uuid:
        from apps.vehicles.models import Vehicle

        vehicle = get_object_or_404(Vehicle.objects.select_related("client"), uuid=vehicle_uuid)
        open_order = (
            ServiceOrder.objects.with_related()
            .in_workshop()
            .filter(vehicle=vehicle)
            .order_by("-entry_at")
            .first()
        )
        if open_order and request.method == "GET":
            messages.info(
                request,
                f"{vehicle.plate_display} já tem {open_order.number_display} aberta.",
            )
            return redirect(open_order.get_absolute_url())

    if request.method == "POST":
        if vehicle is None:
            return HttpResponseBadRequest("Veículo não informado.")

        form = ServiceOrderEntryForm(request.POST)
        if form.is_valid():
            try:
                order = create_service_order(
                    client=vehicle.client,
                    vehicle=vehicle,
                    entry_km=form.cleaned_data["entry_km"],
                    customer_complaint=form.cleaned_data["customer_complaint"],
                    user=request.user,
                    entry_at=form.cleaned_data.get("entry_at"),
                    mechanic=form.cleaned_data.get("mechanic"),
                    expected_delivery_at=form.cleaned_data.get("expected_delivery_at"),
                    location=form.cleaned_data.get("location"),
                    priority=form.cleaned_data.get("priority"),
                    internal_notes=form.cleaned_data.get("internal_notes", ""),
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, f"{order.number_display} aberta para {vehicle.plate_display}.")
                return redirect(order.get_absolute_url())
    else:
        form = ServiceOrderEntryForm()

    context = {
        "page_title": "Nova entrada",
        "vehicle": vehicle,
        "form": form,
        "summary": vehicle_summary(vehicle) if vehicle else None,
    }
    return render(request, "workorders/new_entry.html", context)


@login_required
def new_entry_vehicle(request):
    """Cadastra cliente e veículo quando a placa não existe."""
    if not request.user.can_manage_customers:
        raise PermissionDenied("Seu perfil não pode cadastrar veículos.")

    plate = normalize_plate(request.GET.get("plate", "") or request.POST.get("plate", ""))

    # Quando o cliente já existe, ele vem pela querystring e só os dados do
    # veículo precisam ser preenchidos.
    client_uuid = request.GET.get("client") or request.POST.get("client_uuid") or ""
    selected_client = get_object_or_404(Client, uuid=client_uuid) if client_uuid else None

    client_form = None if selected_client else ClientForm()
    vehicle_form = VehicleForm(initial={"plate": plate})

    if request.method == "POST":
        vehicle_form = VehicleForm(request.POST)
        if not selected_client:
            client_form = ClientForm(request.POST)

        client_ok = selected_client is not None or client_form.is_valid()
        vehicle_ok = vehicle_form.is_valid()

        if client_ok and vehicle_ok:
            with transaction.atomic():
                client = selected_client or client_form.save()
                vehicle = vehicle_form.save(commit=False)
                vehicle.client = client
                vehicle.save()

            messages.success(request, f"{vehicle.plate_display} cadastrado para {client.name}.")
            return redirect(f"{reverse('workorders:new_entry')}?vehicle={vehicle.uuid}")

    return render(
        request,
        "workorders/new_entry_vehicle.html",
        {
            "page_title": "Cadastrar veículo",
            "plate": plate,
            "client_form": client_form,
            "vehicle_form": vehicle_form,
            "selected_client": selected_client,
        },
    )


# --------------------------------------------------------------------------
# Busca global
# --------------------------------------------------------------------------


@login_required
def global_search(request):
    """Busca única do topo: placa, OS, cliente, telefone ou modelo.

    A placa tem prioridade porque é como a oficina identifica um carro. Se o
    termo digitado é exatamente uma placa cadastrada, vamos direto para o
    veículo em vez de mostrar uma lista com um único resultado.
    """
    from apps.vehicles.models import Vehicle

    term = (request.GET.get("q") or "").strip()
    context = {"page_title": "Busca", "term": term}

    if not term:
        return render(request, "workorders/search.html", context)

    plate = normalize_plate(term)
    exact_vehicle = Vehicle.objects.select_related("client").filter(plate=plate).first()
    if exact_vehicle:
        return redirect(exact_vehicle.get_absolute_url())

    # Cada queryset já sabe procurar pelo que lhe interessa: o de OS cobre
    # número e telefone, o de veículo cobre placa parcial, marca e modelo.
    vehicles = list(Vehicle.objects.select_related("client").search(term)[:10])
    clients = list(Client.objects.active().search(term)[:10])
    orders = list(ServiceOrder.objects.with_related().search(term).order_by("-entry_at")[:10])

    context.update(
        {
            "vehicles": vehicles,
            "clients": clients,
            "orders": orders,
            "total": len(vehicles) + len(clients) + len(orders),
        }
    )
    return render(request, "workorders/search.html", context)


# --------------------------------------------------------------------------
# Oficina e detalhe da OS
# --------------------------------------------------------------------------


class WorkshopListView(LoginRequiredMixin, QueryStringMixin, ListView):
    """Mesma informação do Kanban, em lista — melhor para conferência."""

    template_name = "workorders/workshop.html"
    context_object_name = "orders"
    paginate_by = 30

    def get_queryset(self):
        queryset = ServiceOrder.objects.with_related().with_card_data().on_board()
        return apply_filters(queryset, self.request).order_by("entry_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Veículos na oficina"
        context["filters"] = active_filters(self.request)
        context["board_statuses"] = BOARD_STATUSES
        context["mechanics"] = mechanic_queryset()
        context["locations"] = VehicleLocation.objects.filter(is_active=True)
        return context


class HistoryListView(LoginRequiredMixin, QueryStringMixin, ListView):
    """Veículos que já saíram. É aqui que a placa antiga é encontrada."""

    template_name = "workorders/history.html"
    context_object_name = "orders"
    paginate_by = 30

    def get_queryset(self):
        queryset = ServiceOrder.objects.with_related().closed()
        queryset = apply_filters(queryset, self.request)

        start = self._parse_date(self.request.GET.get("start"))
        end = self._parse_date(self.request.GET.get("end"))
        if start:
            queryset = queryset.filter(entry_at__date__gte=start)
        if end:
            queryset = queryset.filter(entry_at__date__lte=end)

        return queryset.order_by("-entry_at")

    @staticmethod
    def _parse_date(value):
        from datetime import date

        raw = (value or "").strip()
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Histórico"
        context["filters"] = active_filters(self.request)
        context["mechanics"] = mechanic_queryset()
        context["start"] = self.request.GET.get("start", "")
        context["end"] = self.request.GET.get("end", "")
        return context


class ServiceOrderDetailView(LoginRequiredMixin, DetailView):
    template_name = "workorders/detail.html"
    context_object_name = "order"

    def get_object(self, queryset=None):
        queryset = ServiceOrder.objects.with_related().prefetch_related(
            "tasks__mechanic", "inspection__items"
        )
        return get_object_or_404(queryset, uuid=self.kwargs["uuid"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object
        inspection = getattr(order, "inspection", None)

        context["page_title"] = order.number_display
        context["activities"] = order.activities.select_related("actor").all()
        context["status_form"] = StatusChangeForm(initial={"status": order.status})
        context["mechanic_form"] = MechanicChangeForm(initial={"mechanic": order.mechanic})
        context["location_form"] = LocationChangeForm(initial={"location": order.location})
        context["delivery_form"] = ExpectedDeliveryForm(
            initial={"expected_delivery_at": order.expected_delivery_at}
        )
        context["diagnosis_form"] = DiagnosisForm(initial={"diagnosis": order.diagnosis})
        context["task_form"] = ServiceTaskForm()
        context["photo_form"] = PhotoUploadForm(initial={"category": _suggested_photo_category(order)})
        context["exit_form"] = DeliveryForm(entry_km=order.entry_km)
        context["cancel_form"] = CancelOrderForm()

        context["tasks"] = order.tasks.all()
        context["progress"] = order.task_progress
        context["photos"] = _grouped_photos(order)
        context["photo_count"] = sum(len(group["photos"]) for group in context["photos"])
        context["inspection"] = inspection
        context["inspection_summary"] = inspection.summary if inspection else None
        context["vehicle_orders"] = (
            order.vehicle.service_orders.with_related().exclude(pk=order.pk).order_by("-entry_at")[:10]
        )
        return context


def _suggested_photo_category(order: ServiceOrder) -> str:
    """Pré-seleciona a categoria conforme o momento da OS.

    Quem está com o celular na mão dentro do box não deveria precisar pensar
    em qual categoria escolher: o status já diz.
    """
    return {
        Status.WAITING_EVALUATION: PhotoCategory.ENTRY,
        Status.IN_EVALUATION: PhotoCategory.DIAGNOSIS,
        Status.WAITING_APPROVAL: PhotoCategory.DIAGNOSIS,
        Status.WAITING_PART: PhotoCategory.SERVICE,
        Status.IN_SERVICE: PhotoCategory.SERVICE,
        Status.FINISHED: PhotoCategory.EXIT,
    }.get(order.status, PhotoCategory.SERVICE)


def _grouped_photos(order: ServiceOrder) -> list:
    """Fotos visíveis agrupadas por categoria, na ordem do fluxo da oficina."""
    photos = list(
        order.photos.visible().select_related("uploaded_by").order_by("created_at", "id")
    )
    groups = []
    for value, label in PhotoCategory.choices:
        bucket = [photo for photo in photos if photo.category == value]
        if bucket:
            groups.append({"value": value, "label": label, "photos": bucket})
    return groups


# --------------------------------------------------------------------------
# Ações rápidas
# --------------------------------------------------------------------------


def _get_order(uuid):
    return get_object_or_404(ServiceOrder.objects.with_related().with_card_data(), uuid=uuid)


def _card_response(request, order):
    """Devolve o card atualizado, usado pelo Kanban depois de mover."""
    return render(request, "dashboard/partials/_order_card.html", {"order": order})


@login_required
@require_POST
def change_status(request, uuid):
    order = _get_order(uuid)
    new_status = request.POST.get("status", "")
    note = request.POST.get("note", "")

    try:
        order = transition_service_order_status(
            order, new_status=new_status, user=request.user, note=note
        )
    except (ValidationError, PermissionDenied) as error:
        message = error.messages[0] if hasattr(error, "messages") else str(error)
        if request.headers.get("HX-Request"):
            return JsonResponse({"error": message}, status=409)
        messages.error(request, message)
        return redirect(order.get_absolute_url())

    label = order.get_status_display()

    if request.headers.get("HX-Request"):
        response = _card_response(request, order)
        response["HX-Trigger"] = _toast_trigger(f"Veículo movido para {label}")
        return response

    messages.success(request, f"Veículo movido para {label}.")
    return redirect(order.get_absolute_url())


def _toast_trigger(message: str) -> str:
    import json

    return json.dumps({"showToast": {"message": message, "level": "success"}})


@login_required
@require_POST
def change_status_from_board(request, uuid):
    """Endpoint do arrastar-e-soltar.

    O backend sempre relê o status atual antes de aplicar a mudança. Se a
    transição não for válida, responde 409 e o card volta para a coluna
    anterior no navegador.
    """
    order = _get_order(uuid)
    new_status = request.POST.get("status", "")

    try:
        order = transition_service_order_status(order, new_status=new_status, user=request.user)
    except (ValidationError, PermissionDenied) as error:
        message = error.messages[0] if hasattr(error, "messages") else str(error)
        return JsonResponse({"error": message, "status": order.status}, status=409)

    return JsonResponse(
        {
            "ok": True,
            "status": order.status,
            "message": f"Veículo movido para {order.get_status_display()}",
        }
    )


@login_required
@require_POST
def change_mechanic_view(request, uuid):
    order = _get_order(uuid)
    form = MechanicChangeForm(request.POST)
    if form.is_valid():
        change_mechanic(order, mechanic=form.cleaned_data["mechanic"], user=request.user)
        messages.success(request, "Mecânico atualizado.")
    else:
        messages.error(request, "Não foi possível atualizar o mecânico.")
    return redirect(order.get_absolute_url())


@login_required
@require_POST
def change_location_view(request, uuid):
    order = _get_order(uuid)
    form = LocationChangeForm(request.POST)
    if form.is_valid():
        change_location(order, location=form.cleaned_data["location"], user=request.user)
        messages.success(request, "Localização atualizada.")
    else:
        messages.error(request, "Não foi possível atualizar a localização.")
    return redirect(order.get_absolute_url())


@login_required
@require_POST
def change_delivery_view(request, uuid):
    order = _get_order(uuid)
    form = ExpectedDeliveryForm(request.POST)
    if form.is_valid():
        change_expected_delivery(
            order, expected_delivery_at=form.cleaned_data["expected_delivery_at"], user=request.user
        )
        messages.success(request, "Previsão atualizada.")
    else:
        messages.error(request, "Previsão inválida.")
    return redirect(order.get_absolute_url())


@login_required
@require_POST
def update_diagnosis_view(request, uuid):
    order = _get_order(uuid)
    form = DiagnosisForm(request.POST)
    if form.is_valid():
        update_diagnosis(order, diagnosis=form.cleaned_data["diagnosis"], user=request.user)
        messages.success(request, "Diagnóstico salvo.")
    else:
        messages.error(request, "Não foi possível salvar o diagnóstico.")
    return redirect(order.get_absolute_url() + "#diagnostico")


# --------------------------------------------------------------------------
# Serviços da OS
# --------------------------------------------------------------------------


def _tasks_response(request, order):
    """Devolve a lista de serviços renderizada, para o HTMX trocar em tela."""
    order.refresh_from_db()
    return render(
        request,
        "workorders/partials/_tasks.html",
        {
            "order": order,
            "tasks": order.tasks.select_related("mechanic").all(),
            "progress": order.task_progress,
            "task_form": ServiceTaskForm(),
        },
    )


def _task_redirect(order):
    return redirect(order.get_absolute_url() + "#servicos")


@login_required
@require_POST
def add_task_view(request, uuid):
    order = _get_order(uuid)
    form = ServiceTaskForm(request.POST)

    if form.is_valid():
        try:
            add_service_task(
                order,
                title=form.cleaned_data["title"],
                requested_description=form.cleaned_data.get("requested_description", ""),
                mechanic=form.cleaned_data.get("mechanic"),
                user=request.user,
            )
        except (ValidationError, PermissionDenied) as error:
            messages.error(request, _first_message(error))
        else:
            messages.success(request, "Serviço adicionado.")
    else:
        messages.error(request, "Informe o serviço que será executado.")

    if request.headers.get("HX-Request"):
        return _tasks_response(request, order)
    return _task_redirect(order)


@login_required
@require_POST
def task_action_view(request, uuid, task_id, action):
    """Concluir, iniciar, reabrir ou cancelar um serviço."""
    order = _get_order(uuid)
    task = get_object_or_404(ServiceTask, pk=task_id, service_order=order)

    handlers = {
        "iniciar": lambda: start_service_task(task, user=request.user),
        "concluir": lambda: complete_service_task(
            task,
            user=request.user,
            performed_service=request.POST.get("performed_service", ""),
        ),
        "reabrir": lambda: reopen_service_task(task, user=request.user),
        "cancelar": lambda: cancel_service_task(task, user=request.user),
    }
    handler = handlers.get(action)
    if handler is None:
        return HttpResponseBadRequest("Ação inválida.")

    try:
        handler()
    except (ValidationError, PermissionDenied) as error:
        messages.error(request, _first_message(error))
    else:
        messages.success(request, "Serviço atualizado.")

    if request.headers.get("HX-Request"):
        return _tasks_response(request, order)
    return _task_redirect(order)


# --------------------------------------------------------------------------
# Fotos
# --------------------------------------------------------------------------


@login_required
@require_POST
def upload_photos_view(request, uuid):
    order = _get_order(uuid)
    form = PhotoUploadForm(request.POST, request.FILES)

    if form.is_valid():
        try:
            created = add_photos(
                order,
                images=form.cleaned_data["images"],
                category=form.cleaned_data["category"],
                caption=form.cleaned_data.get("caption", ""),
                angle=form.cleaned_data.get("angle") or "",
                user=request.user,
            )
        except (ValidationError, PermissionDenied) as error:
            messages.error(request, _first_message(error))
        else:
            quantity = len(created)
            messages.success(
                request, f"{quantity} foto{'s' if quantity > 1 else ''} adicionada{'s' if quantity > 1 else ''}."
            )
    else:
        for error in form.errors.get("images", []) or ["Não foi possível enviar as fotos."]:
            messages.error(request, error)

    return redirect(order.get_absolute_url() + "#fotos")


@login_required
@require_POST
def remove_photo_view(request, uuid, photo_id):
    order = _get_order(uuid)
    photo = get_object_or_404(ServiceOrderPhoto, pk=photo_id, service_order=order, is_deleted=False)

    try:
        remove_photo(photo, user=request.user)
    except PermissionDenied as error:
        messages.error(request, _first_message(error))
    else:
        messages.success(request, "Foto removida do registro.")

    return redirect(order.get_absolute_url() + "#fotos")


# --------------------------------------------------------------------------
# Vistoria
# --------------------------------------------------------------------------


@login_required
def inspection_view(request, uuid):
    order = _get_order(uuid)

    if not request.user.can_perform_inspection:
        raise PermissionDenied("Seu perfil não pode registrar vistoria.")

    if not order.is_open:
        messages.error(request, "Esta OS já está fechada e não aceita vistoria.")
        return redirect(order.get_absolute_url() + "#vistoria")

    inspection = get_or_build_inspection(order)
    items = list(inspection.items.all())

    if request.method == "POST":
        form = InspectionForm(request.POST, items=items)
        if form.is_valid():
            try:
                save_inspection(
                    order,
                    conditions=form.conditions,
                    notes_by_key=form.item_notes,
                    fuel_level=form.cleaned_data["fuel_level"],
                    notes=form.cleaned_data.get("notes", ""),
                    user=request.user,
                )
            except (ValidationError, PermissionDenied) as error:
                messages.error(request, _first_message(error))
            else:
                messages.success(request, "Vistoria registrada.")
                return redirect(order.get_absolute_url() + "#vistoria")
    else:
        form = InspectionForm(
            items=items,
            initial={"fuel_level": inspection.fuel_level, "notes": inspection.notes},
        )

    return render(
        request,
        "workorders/inspection.html",
        {
            "page_title": f"Vistoria — {order.number_display}",
            "order": order,
            "inspection": inspection,
            "form": form,
        },
    )


# --------------------------------------------------------------------------
# Finalização, saída e cancelamento
# --------------------------------------------------------------------------


@login_required
@require_POST
def finalize_view(request, uuid):
    order = _get_order(uuid)
    try:
        finalize_service_order(order, user=request.user, note=request.POST.get("note", ""))
    except (ValidationError, PermissionDenied) as error:
        messages.error(request, _first_message(error))
    else:
        messages.success(request, "Serviço finalizado. O veículo continua na oficina.")
    return redirect(order.get_absolute_url())


@login_required
def delivery_view(request, uuid):
    """Registrar saída. Tela própria porque exige conferência de dados."""
    order = _get_order(uuid)

    if not request.user.can_deliver_vehicle:
        raise PermissionDenied("Seu perfil não pode registrar a saída do veículo.")

    if not order.is_open:
        messages.info(request, f"Esta OS já está {order.get_status_display().lower()}.")
        return redirect(order.get_absolute_url())

    if request.method == "POST":
        form = DeliveryForm(request.POST, entry_km=order.entry_km)
        if form.is_valid():
            try:
                deliver_vehicle(
                    order,
                    user=request.user,
                    exit_km=form.cleaned_data["exit_km"],
                    delivered_at=form.cleaned_data["delivered_at"],
                    exit_notes=form.cleaned_data.get("exit_notes", ""),
                    exit_km_justification=form.cleaned_data.get("exit_km_justification", ""),
                    received_by_name=form.cleaned_data.get("received_by_name", ""),
                    received_by_document=form.cleaned_data.get("received_by_document", ""),
                    signature=form.cleaned_data.get("signature"),
                )
            except ValidationError as error:
                form.add_error(None, error)
            except PermissionDenied as error:
                messages.error(request, _first_message(error))
                return redirect(order.get_absolute_url())
            else:
                messages.success(
                    request, f"{order.vehicle.plate_display} entregue. {order.number_display} encerrada."
                )
                return redirect(order.get_absolute_url())
    else:
        form = DeliveryForm(entry_km=order.entry_km)

    return render(
        request,
        "workorders/delivery.html",
        {
            "page_title": f"Registrar saída — {order.number_display}",
            "order": order,
            "form": form,
            "progress": order.task_progress,
            "open_tasks": order.tasks.filter(
                status__in=[TaskStatus.PENDING, TaskStatus.RUNNING]
            ),
        },
    )


@login_required
@require_POST
def cancel_view(request, uuid):
    order = _get_order(uuid)
    form = CancelOrderForm(request.POST)

    if form.is_valid():
        try:
            cancel_service_order(
                order, user=request.user, reason=form.cleaned_data["cancellation_reason"]
            )
        except (ValidationError, PermissionDenied) as error:
            messages.error(request, _first_message(error))
        else:
            messages.success(request, f"{order.number_display} cancelada.")
    else:
        messages.error(request, "Informe o motivo do cancelamento.")

    return redirect(order.get_absolute_url())


def _first_message(error) -> str:
    return error.messages[0] if hasattr(error, "messages") else str(error)
