"""Views do PWA de recepção no pátio.

Primeiro contato (entrada + vistoria) no celular; detalhes complexos no notebook.
Reutiliza os mesmos models e services do desktop.
"""

import logging

from django import forms
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.customers.models import Client
from apps.customers.services import find_by_phone
from apps.vehicles.models import Vehicle, normalize_plate
from apps.vehicles.services import build_plate_lookup_context, find_by_plate, vehicle_summary
from apps.workorders.forms import InspectionForm, PhotoUploadForm
from apps.workorders.models import (
    GUIDED_PHOTO_ANGLES,
    ItemCondition,
    PhotoAngle,
    PhotoCategory,
    ServiceOrder,
    ServiceOrderPhoto,
)
from apps.workorders.services import (
    add_photos,
    create_service_order,
    get_or_build_inspection,
    save_inspection,
)

from .forms import MobileNewEntryForm, MobileReturningEntryForm

logger = logging.getLogger(__name__)


def _mobile_inspection_form(*args, items=None, **kwargs):
    """InspectionForm com combustível em radio (chips touch no celular)."""
    form = InspectionForm(*args, items=items, **kwargs)
    form.fields["fuel_level"].widget = forms.RadioSelect()
    form.fields["notes"].widget.attrs.update(
        {
            "rows": 3,
            "placeholder": "Opcional — observações gerais da entrada",
            "class": "m-textarea",
        }
    )
    for item in form.items:
        note = form.fields[f"note_{item.key}"]
        note.widget.attrs.update(
            {
                "placeholder": "Descreva a observação",
                "class": "m-note-input",
                "inputmode": "text",
            }
        )
    return form


def _first_message(error) -> str:
    return error.messages[0] if hasattr(error, "messages") else str(error)


def _get_order(uuid):
    return get_object_or_404(ServiceOrder.objects.with_related(), uuid=uuid)


def _open_order_for_vehicle(vehicle: Vehicle):
    return (
        ServiceOrder.objects.with_related()
        .in_workshop()
        .filter(vehicle=vehicle)
        .order_by("-entry_at")
        .first()
    )


def _workshop_orders_for_inspection(term: str = ""):
    """OS abertas, com prioridade para quem ainda precisa de vistoria."""
    queryset = (
        ServiceOrder.objects.with_related()
        .in_workshop()
        .annotate(
            unchecked_items=Count(
                "inspection__items",
                filter=Q(inspection__items__condition=ItemCondition.NOT_CHECKED),
            ),
            has_inspection=Count("inspection"),
        )
    )

    term = (term or "").strip()
    if term:
        queryset = queryset.search(term)
        plate = normalize_plate(term)
        if plate:
            exact = list(queryset.filter(vehicle__plate=plate).order_by("-entry_at")[:5])
            if exact:
                return exact

    return list(
        queryset.order_by("has_inspection", "-unchecked_items", "entry_at")[:40]
    )


# ---------------------------------------------------------------------------
# Home / instalar (público)
# ---------------------------------------------------------------------------


@require_GET
@never_cache
def install(request):
    """Página pública para instalar o PWA — link do WhatsApp no celular.

    Estilo Agro `/ajuste-mobile/`: card central com Instalar.
    Sem login. Já instalado (standalone) → manda para a home do app.
    """
    return render(
        request,
        "mobile/install.html",
        {
            "page_title": "Instalar",
            "continue_url": reverse("mobile:home"),
            "login_url": f"{reverse('accounts:login')}?next={reverse('mobile:home')}",
        },
    )


@login_required
@never_cache
def home(request):
    if not request.user.can_perform_inspection and not request.user.can_register_entry:
        raise PermissionDenied("Seu perfil não pode usar o app de recepção.")

    term = (request.GET.get("q") or "").strip()
    orders = _workshop_orders_for_inspection(term)

    if term and len(orders) == 1:
        return redirect("mobile:inspection", uuid=orders[0].uuid)

    return render(
        request,
        "mobile/home.html",
        {
            "page_title": "Recepção",
            "term": term,
            "orders": orders,
        },
    )


# ---------------------------------------------------------------------------
# Nova entrada (primeiro contato)
# ---------------------------------------------------------------------------


@login_required
@never_cache
def entry_start(request):
    """Passo 1: identificar o veículo pela placa."""
    if not request.user.can_register_entry:
        raise PermissionDenied("Seu perfil não pode registrar entradas.")

    return render(
        request,
        "mobile/entry_start.html",
        {"page_title": "Nova entrada"},
    )


@login_required
@never_cache
def entry_plate_lookup(request):
    """HTMX: resultado da busca por placa no fluxo mobile."""
    if not request.user.can_register_entry:
        raise PermissionDenied("Seu perfil não pode registrar entradas.")

    raw = request.GET.get("plate", "")
    plate = normalize_plate(raw)
    context = build_plate_lookup_context(plate=plate, raw=raw)
    return render(request, "mobile/partials/_plate_lookup.html", context)


@login_required
@require_POST
def entry_read_plate(request):
    """Recebe foto da placa e devolve o texto lido (JSON)."""
    if not request.user.can_register_entry:
        raise PermissionDenied("Seu perfil não pode registrar entradas.")

    upload = request.FILES.get("image") or request.FILES.get("photo")
    if upload is None:
        return JsonResponse({"ok": False, "error": "Envie uma foto da placa."}, status=400)

    try:
        from .plate_ocr import read_plate_from_upload

        result = read_plate_from_upload(upload)
    except ValidationError as error:
        message = error.messages[0] if hasattr(error, "messages") else str(error)
        return JsonResponse({"ok": False, "error": message}, status=422)

    return JsonResponse(
        {
            "ok": True,
            "plate": result["plate"],
            "confidence": result["confidence"],
        }
    )


@login_required
@require_POST
def entry_warmup_ocr(request):
    """Pré-carrega o modelo ONNX ao abrir a tela da placa (não no boot).

    Evita a espera longa na 1ª foto sem arriscar 502 no health check do Render.
    """
    if not request.user.can_register_entry:
        raise PermissionDenied("Seu perfil não pode registrar entradas.")

    from django.conf import settings

    if not getattr(settings, "ENABLE_PLATE_OCR", False):
        return JsonResponse({"ok": True, "warmed": False, "reason": "disabled"})

    try:
        from .plate_ocr import warmup_engine

        warmup_engine()
    except ValidationError as error:
        message = error.messages[0] if hasattr(error, "messages") else str(error)
        return JsonResponse({"ok": False, "warmed": False, "error": message}, status=422)
    except Exception:
        logger.exception("Warmup OCR sob demanda falhou")
        return JsonResponse({"ok": False, "warmed": False}, status=500)

    return JsonResponse({"ok": True, "warmed": True})


@login_required
@never_cache
def entry_existing(request, uuid):
    """Veículo já cadastrado: confirma telefone, KM e queixa → abre OS → vistoria."""
    if not request.user.can_register_entry:
        raise PermissionDenied("Seu perfil não pode registrar entradas.")

    vehicle = get_object_or_404(Vehicle.objects.select_related("client"), uuid=uuid)
    open_order = _open_order_for_vehicle(vehicle)
    if open_order:
        messages.info(
            request,
            f"{vehicle.plate_display} já tem {open_order.number_display} aberta. Continue a vistoria.",
        )
        return redirect("mobile:inspection", uuid=open_order.uuid)

    client = vehicle.client
    summary = vehicle_summary(vehicle)

    if request.method == "POST":
        form = MobileReturningEntryForm(request.POST, client=client)
        if form.is_valid():
            try:
                with transaction.atomic():
                    name = form.cleaned_data["name"]
                    phone = form.cleaned_data["phone"]
                    updates = []
                    if name != client.name:
                        client.name = name
                        updates.append("name")
                    if phone != client.phone:
                        client.phone = phone
                        updates.append("phone")
                    if updates:
                        client.save(update_fields=[*updates, "updated_at"])
                    order = create_service_order(
                        client=client,
                        vehicle=vehicle,
                        entry_km=form.cleaned_data["entry_km"],
                        customer_complaint=form.cleaned_data["customer_complaint"],
                        priority=form.cleaned_data.get("priority"),
                        brought_by_name=form.cleaned_data.get("brought_by_name") or "",
                        user=request.user,
                    )
            except (ValidationError, PermissionDenied) as error:
                form.add_error(None, _first_message(error))
            else:
                messages.success(
                    request,
                    f"{order.number_display} aberta. Agora faça a vistoria.",
                )
                return redirect("mobile:inspection", uuid=order.uuid)
    else:
        form = MobileReturningEntryForm(client=client)

    return render(
        request,
        "mobile/entry_existing.html",
        {
            "page_title": "Confirmar entrada",
            "vehicle": vehicle,
            "client": client,
            "summary": summary,
            "form": form,
        },
    )


@login_required
@never_cache
def entry_new(request):
    """Placa nova: cliente + veículo + KM/queixa num único formulário."""
    if not request.user.can_register_entry:
        raise PermissionDenied("Seu perfil não pode registrar entradas.")
    if not request.user.can_manage_customers:
        raise PermissionDenied("Seu perfil não pode cadastrar clientes e veículos.")

    plate = normalize_plate(request.GET.get("plate", "") or request.POST.get("plate", ""))
    if plate:
        existing = find_by_plate(plate)
        if existing:
            return redirect("mobile:entry_existing", uuid=existing.uuid)

    if request.method == "POST":
        form = MobileNewEntryForm(request.POST, initial_plate=plate)
        if form.is_valid():
            data = form.cleaned_data
            try:
                with transaction.atomic():
                    matches = list(find_by_phone(data["phone"])[:1])
                    if matches:
                        client = matches[0]
                        client.name = data["name"]
                        client.phone_whatsapp = data.get("phone_whatsapp") or ""
                        client.save()
                    else:
                        client = Client.objects.create(
                            name=data["name"],
                            phone=data["phone"],
                            phone_whatsapp=data.get("phone_whatsapp") or "",
                        )

                    vehicle = Vehicle.objects.create(
                        client=client,
                        plate=data["plate"],
                        brand=data["brand"],
                        model=data["model"],
                        color=data.get("color") or "",
                        model_year=data.get("model_year"),
                    )
                    order = create_service_order(
                        client=client,
                        vehicle=vehicle,
                        entry_km=data["entry_km"],
                        customer_complaint=data["customer_complaint"],
                        priority=data.get("priority"),
                        brought_by_name=data.get("brought_by_name") or "",
                        user=request.user,
                    )
            except (ValidationError, PermissionDenied) as error:
                form.add_error(None, _first_message(error))
            else:
                messages.success(
                    request,
                    f"{order.number_display} aberta. Agora faça a vistoria.",
                )
                return redirect("mobile:inspection", uuid=order.uuid)
    else:
        form = MobileNewEntryForm(initial_plate=plate)

    return render(
        request,
        "mobile/entry_new.html",
        {
            "page_title": "Cadastrar entrada",
            "form": form,
            "plate": plate,
        },
    )


# ---------------------------------------------------------------------------
# Vistoria
# ---------------------------------------------------------------------------


@login_required
@never_cache
def inspection(request, uuid):
    order = _get_order(uuid)

    if not request.user.can_perform_inspection:
        raise PermissionDenied("Seu perfil não pode registrar vistoria.")

    if not order.is_open:
        messages.error(request, "Esta OS já foi encerrada.")
        return redirect("mobile:home")

    inspection_obj = get_or_build_inspection(order)
    items = list(inspection_obj.items.all())

    if request.method == "POST":
        form = _mobile_inspection_form(request.POST, items=items)
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
                messages.success(request, "Vistoria salva. Entrada concluída no celular.")
                return redirect("mobile:home")
    else:
        form = _mobile_inspection_form(
            items=items,
            initial={"fuel_level": inspection_obj.fuel_level, "notes": inspection_obj.notes},
        )

    photos = list(
        order.photos.visible()
        .filter(category=PhotoCategory.INSPECTION)
        .select_related("uploaded_by")
        .order_by("-created_at", "-id")
    )
    guided_slots = _guided_photo_slots(photos)

    return render(
        request,
        "mobile/inspection.html",
        {
            "page_title": f"Vistoria {order.number_display}",
            "order": order,
            "inspection": inspection_obj,
            "form": form,
            "photos": photos,
            "guided_slots": guided_slots,
            "extra_photos": [p for p in photos if p.angle == PhotoAngle.EXTRA or not p.angle],
            "summary": inspection_obj.summary,
            "guided_done": sum(1 for slot in guided_slots if slot["photo"]),
            "guided_total": len(guided_slots),
        },
    )


def _guided_photo_slots(photos):
    """Monta os 5 slots obrigatórios com a foto atual de cada ângulo."""
    guided_keys = {angle.value for angle in GUIDED_PHOTO_ANGLES}
    by_angle = {}
    for photo in photos:
        if photo.angle in guided_keys and photo.angle not in by_angle:
            by_angle[photo.angle] = photo
    return [
        {
            "angle": angle.value,
            "label": angle.label,
            "hint": _ANGLE_HINTS.get(angle.value, ""),
            "example": _ANGLE_EXAMPLES.get(angle.value, ""),
            "photo": by_angle.get(angle.value),
        }
        for angle in GUIDED_PHOTO_ANGLES
    ]


_ANGLE_HINTS = {
    PhotoAngle.FRONT: "Carro de frente, inteiro no quadro",
    PhotoAngle.REAR: "Carro de trás, placa visível",
    PhotoAngle.LEFT: "Lado do motorista, de ponta a ponta",
    PhotoAngle.RIGHT: "Lado do passageiro, de ponta a ponta",
    PhotoAngle.DIAGONAL: "¾ dianteira (canto + frente)",
}

_ANGLE_EXAMPLES = {
    PhotoAngle.FRONT: "mobile/shots/frente.svg",
    PhotoAngle.REAR: "mobile/shots/traseira.svg",
    PhotoAngle.LEFT: "mobile/shots/lateral_esq.svg",
    PhotoAngle.RIGHT: "mobile/shots/lateral_dir.svg",
    PhotoAngle.DIAGONAL: "mobile/shots/diagonal.svg",
}


@login_required
@require_POST
def upload_photos(request, uuid):
    order = _get_order(uuid)

    if not request.user.can_upload_photos:
        raise PermissionDenied("Seu perfil não pode enviar fotos.")

    if not order.is_open:
        messages.error(request, "Esta OS já foi encerrada.")
        return redirect("mobile:home")

    post = request.POST.copy()
    post["category"] = PhotoCategory.INSPECTION
    form = PhotoUploadForm(post, request.FILES)

    if form.is_valid():
        try:
            created = add_photos(
                order,
                images=form.cleaned_data["images"],
                category=PhotoCategory.INSPECTION,
                caption=form.cleaned_data.get("caption", ""),
                angle=form.cleaned_data.get("angle") or PhotoAngle.EXTRA,
                user=request.user,
            )
        except (ValidationError, PermissionDenied) as error:
            messages.error(request, _first_message(error))
        else:
            quantity = len(created)
            messages.success(
                request,
                f"{quantity} foto{'s' if quantity > 1 else ''} adicionada{'s' if quantity > 1 else ''}.",
            )
    else:
        for error in form.errors.get("images", []) or ["Não foi possível enviar as fotos."]:
            messages.error(request, error)

    if request.headers.get("HX-Request"):
        return _photos_partial(request, order)

    return redirect("mobile:inspection", uuid=order.uuid)


def _photos_partial(request, order):
    photos = list(
        order.photos.visible()
        .filter(category=PhotoCategory.INSPECTION)
        .order_by("-created_at", "-id")
    )
    return render(
        request,
        "mobile/partials/_photos.html",
        {
            "order": order,
            "photos": photos,
            "guided_slots": _guided_photo_slots(photos),
            "extra_photos": [p for p in photos if p.angle == PhotoAngle.EXTRA or not p.angle],
            "guided_done": sum(1 for slot in _guided_photo_slots(photos) if slot["photo"]),
            "guided_total": len(GUIDED_PHOTO_ANGLES),
        },
    )


@login_required
@require_POST
def remove_photo(request, uuid, photo_id):
    from apps.workorders.services import remove_photo as remove_photo_service

    order = _get_order(uuid)
    photo = get_object_or_404(
        ServiceOrderPhoto, pk=photo_id, service_order=order, is_deleted=False
    )

    try:
        remove_photo_service(photo, user=request.user)
    except PermissionDenied as error:
        messages.error(request, _first_message(error))
    else:
        messages.success(request, "Foto removida.")

    if request.headers.get("HX-Request"):
        return _photos_partial(request, order)

    return redirect("mobile:inspection", uuid=order.uuid)


# ---------------------------------------------------------------------------
# Perfil (dentro do app — sem cair no desktop)
# ---------------------------------------------------------------------------


@login_required
@never_cache
def profile(request):
    return render(
        request,
        "mobile/profile.html",
        {"page_title": "Perfil"},
    )


@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect(f"{reverse('accounts:login')}?next={reverse('mobile:home')}")


# ---------------------------------------------------------------------------
# PWA
# ---------------------------------------------------------------------------


@require_GET
def manifest(request):
    icon_192 = request.build_absolute_uri("/static/mobile/icons/icon-192.png")
    icon_512 = request.build_absolute_uri("/static/mobile/icons/icon-512.png")
    start = request.build_absolute_uri(reverse("mobile:home"))
    payload = {
        "name": "DR Vistoria",
        "short_name": "Vistoria",
        "description": "Recepção e vistoria de entrada — DR Centro Automotivo",
        "start_url": start,
        "scope": request.build_absolute_uri("/m/"),
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#0b1838",
        "theme_color": "#0b1838",
        "lang": "pt-BR",
        "icons": [
            {
                "src": f"{icon_192}?v=2",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": f"{icon_512}?v=2",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": f"{icon_192}?v=2",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "maskable",
            },
            {
                "src": f"{icon_512}?v=2",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    return JsonResponse(payload, content_type="application/manifest+json")


@require_GET
def service_worker(request):
    path = finders.find("mobile/sw.js")
    if not path:
        return HttpResponse("// sw missing", content_type="application/javascript", status=404)
    response = FileResponse(
        open(path, "rb"),
        content_type="application/javascript",
        as_attachment=False,
        filename="sw.js",
    )
    response["Service-Worker-Allowed"] = "/m/"
    response["Cache-Control"] = "no-cache"
    return response
