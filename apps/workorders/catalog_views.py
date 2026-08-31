"""Cadastro rápido de mecânico e localização (HTMX, estilo combobox + criar)."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.services import create_mechanic_user
from apps.vehicles.services import create_location

from .forms import (
    QuickLocationForm,
    QuickMechanicForm,
    location_select_field,
    mechanic_select_field,
)


def _catalog_context(request, *, kind: str):
    target_id = (request.GET.get("target_id") or request.POST.get("target_id") or "").strip()
    field_name = (request.GET.get("field_name") or request.POST.get("field_name") or "").strip()
    empty_label = (
        request.GET.get("empty_label") or request.POST.get("empty_label") or ""
    ).strip()
    selected = request.GET.get("selected") or request.POST.get("selected") or ""

    if kind == "mechanic":
        if not empty_label:
            empty_label = "Sem responsável"
        if not field_name:
            field_name = "mechanic"
    else:
        if not empty_label:
            empty_label = "Sem localização"
        if not field_name:
            field_name = "location"

    selected_value = selected or None
    if selected_value == "":
        selected_value = None
    if kind == "location" and selected_value is not None:
        try:
            selected_value = int(selected_value)
        except (TypeError, ValueError):
            selected_value = None
    if kind == "mechanic" and selected_value is not None:
        try:
            selected_value = int(selected_value)
        except (TypeError, ValueError):
            selected_value = None

    return {
        "target_id": target_id or f"creatable-{kind}",
        "field_name": field_name,
        "empty_label": empty_label,
        "selected": selected_value,
    }


def _apply_service_errors(form, error: ValidationError):
    if hasattr(error, "message_dict"):
        for field, messages in error.message_dict.items():
            if field in form.fields:
                if isinstance(messages, (list, tuple)):
                    form.add_error(field, messages[0])
                else:
                    form.add_error(field, messages)
            else:
                form.add_error(None, messages if isinstance(messages, str) else messages[0])
    else:
        form.add_error(None, error.messages[0] if error.messages else str(error))


def _creatable_mechanic_context(request, *, selected=None):
    ctx = _catalog_context(request, kind="mechanic")
    ctx["field"] = mechanic_select_field(selected=selected, empty_label=ctx["empty_label"])
    ctx["can_create"] = request.user.can_manage_users
    ctx["create_label"] = "Cadastrar mecânico"
    return ctx


def _creatable_location_context(request, *, selected=None):
    ctx = _catalog_context(request, kind="location")
    ctx["field"] = location_select_field(selected=selected, empty_label=ctx["empty_label"])
    ctx["can_create"] = request.user.can_register_entry
    ctx["create_label"] = "Cadastrar localização"
    return ctx


@login_required
@require_GET
def quick_mechanic_panel(request):
    if not request.user.can_manage_users:
        return HttpResponseForbidden("Seu perfil não pode cadastrar mecânicos.")

    ctx = _catalog_context(request, kind="mechanic")
    ctx["form"] = QuickMechanicForm()
    return render(request, "workorders/partials/_quick_mechanic_panel.html", ctx)


@login_required
@require_POST
def quick_mechanic_create(request):
    if not request.user.can_manage_users:
        return HttpResponseForbidden("Seu perfil não pode cadastrar mecânicos.")

    ctx_base = _catalog_context(request, kind="mechanic")
    form = QuickMechanicForm(request.POST)

    if form.is_valid():
        try:
            mechanic = create_mechanic_user(
                name=form.cleaned_data["name"],
                username=form.cleaned_data["username"],
                pin=form.cleaned_data["pin"],
                phone=form.cleaned_data.get("phone") or "",
                actor=request.user,
            )
        except ValidationError as error:
            _apply_service_errors(form, error)
        except PermissionDenied as error:
            form.add_error(None, str(error))
        else:
            ctx = _creatable_mechanic_context(request, selected=mechanic.pk)
            return render(request, "workorders/partials/_creatable_mechanic_oob.html", ctx)

    ctx = {**ctx_base, "form": form}
    return render(request, "workorders/partials/_quick_mechanic_panel.html", ctx)


@login_required
@require_GET
def quick_location_panel(request):
    if not request.user.can_register_entry:
        return HttpResponseForbidden("Seu perfil não pode cadastrar localizações.")

    ctx = _catalog_context(request, kind="location")
    ctx["form"] = QuickLocationForm()
    return render(request, "workorders/partials/_quick_location_panel.html", ctx)


@login_required
@require_POST
def quick_location_create(request):
    if not request.user.can_register_entry:
        return HttpResponseForbidden("Seu perfil não pode cadastrar localizações.")

    ctx_base = _catalog_context(request, kind="location")
    form = QuickLocationForm(request.POST)

    if form.is_valid():
        try:
            location = create_location(name=form.cleaned_data["name"], actor=request.user)
        except ValidationError as error:
            _apply_service_errors(form, error)
        except PermissionDenied as error:
            form.add_error(None, str(error))
        else:
            ctx = _creatable_location_context(request, selected=location.pk)
            return render(request, "workorders/partials/_creatable_location_oob.html", ctx)

    ctx = {**ctx_base, "form": form}
    return render(request, "workorders/partials/_quick_location_panel.html", ctx)
