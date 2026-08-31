"""Aba Configurações — somente administradores."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.forms import OperationalUserCreateForm, UserPinResetForm
from apps.accounts.models import Role, User
from apps.accounts.services import create_operational_user, set_user_pin
from apps.core.models import WorkshopSettings
from apps.core.services.demo_purge import purge_demo_data
from apps.core.services.demo_seed import DemoDataAlreadyLoaded, load_demo_data
from apps.core.services.settings import get_workshop_settings, invalidate_workshop_settings_cache
from apps.core.spreadsheet import build_export_workbook, import_uploaded_file
from apps.customers.models import Client
from apps.vehicles.models import Vehicle, VehicleLocation
from apps.vehicles.services import create_location
from apps.workorders.catalog_views import _apply_service_errors
from apps.workorders.forms import QuickLocationForm
from apps.workorders.models import ServiceOrder

from .settings_forms import DemoPurgeForm, SpreadsheetUploadForm, WorkshopPreferencesForm


def _require_admin(user):
    if not user.can_manage_users:
        raise PermissionDenied("Somente administradores acessam Configurações.")


@login_required
@require_GET
def settings_index(request):
    try:
        _require_admin(request.user)
    except PermissionDenied as error:
        return HttpResponseForbidden(str(error))

    cards = [
        {
            "title": "Preferências",
                "description": "Recepção, mecânicos, PINs e aviso WhatsApp ao mudar status.",
            "url_name": "core:settings_preferences",
            "icon": "⚙",
        },
        {
            "title": "Usuários e PINs",
            "description": "Cadastrar recepção, administradores e mecânicos; redefinir PIN de login.",
            "url_name": "core:settings_users",
            "icon": "👤",
        },
        {
            "title": "Localizações",
            "description": "Onde o carro fica no pátio (elevador, box, pátio externo…).",
            "url_name": "core:settings_locations",
            "icon": "📍",
        },
        {
            "title": "Planilhas de cadastro",
            "description": "Baixar modelo, exportar cadastros e importar alterações via Excel.",
            "url_name": "core:settings_spreadsheets",
            "icon": "📊",
        },
        {
            "title": "Dados de exemplo",
            "description": "Carregar ou limpar clientes, veículos e OS de demonstração.",
            "url_name": "core:settings_demo",
            "icon": "🧪",
        },
        {
            "title": "Administração avançada",
            "description": "Painel Django para manutenção técnica de dados.",
            "href": "/admin/",
            "icon": "🛠",
        },
    ]

    return render(
        request,
        "settings/index.html",
        {
            "cards": cards,
            "user_count": User.objects.filter(is_active=True).count(),
            "mechanic_count": User.objects.filter(role=Role.MECHANIC, is_active=True).count(),
            "location_count": VehicleLocation.objects.filter(is_active=True).count(),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def settings_preferences(request):
    if not request.user.can_manage_users:
        return HttpResponseForbidden("Somente administradores alteram preferências.")

    settings_obj = get_workshop_settings()
    if request.method == "POST":
        form = WorkshopPreferencesForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            invalidate_workshop_settings_cache()
            messages.success(request, "Preferências salvas.")
            return redirect("core:settings_preferences")
    else:
        form = WorkshopPreferencesForm(instance=settings_obj)

    return render(request, "settings/preferences.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def settings_users(request):
    if not request.user.can_manage_users:
        return HttpResponseForbidden("Somente administradores gerenciam usuários.")

    users = User.objects.order_by("first_name", "username")
    form = OperationalUserCreateForm()

    if request.method == "POST":
        form = OperationalUserCreateForm(request.POST)
        if form.is_valid():
            try:
                create_operational_user(
                    name=form.cleaned_data["name"],
                    username=form.cleaned_data["username"],
                    role=form.cleaned_data["role"],
                    pin=form.cleaned_data["pin"],
                    phone=form.cleaned_data.get("phone") or "",
                    actor=request.user,
                )
            except ValidationError as error:
                _apply_service_errors(form, error)
            except PermissionDenied as error:
                form.add_error(None, str(error))
            else:
                messages.success(request, "Usuário cadastrado.")
                return redirect("core:settings_users")
        else:
            messages.error(request, "Corrija os campos destacados.")

    return render(
        request,
        "settings/users.html",
        {"form": form, "users": users, "pin_form": UserPinResetForm()},
    )


@login_required
@require_POST
def settings_user_pin(request, user_uuid):
    if not request.user.can_manage_users:
        return HttpResponseForbidden("Somente administradores alteram PINs.")

    target = get_object_or_404(User, uuid=user_uuid)
    form = UserPinResetForm(request.POST)

    if form.is_valid():
        try:
            set_user_pin(target=target, pin=form.cleaned_data["pin"], actor=request.user)
        except ValidationError as error:
            _apply_service_errors(form, error)
            messages.error(request, "Não foi possível alterar o PIN.")
        except PermissionDenied as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f"PIN de {target.display_name} atualizado.")
    else:
        messages.error(request, "Informe um PIN válido de 4 dígitos.")

    return redirect("core:settings_users")


@login_required
@require_http_methods(["GET", "POST"])
def settings_locations(request):
    if not request.user.can_manage_users:
        return HttpResponseForbidden("Somente administradores cadastram localizações.")

    locations = VehicleLocation.objects.order_by("order", "name")
    form = QuickLocationForm()

    if request.method == "POST":
        form = QuickLocationForm(request.POST)
        if form.is_valid():
            try:
                create_location(name=form.cleaned_data["name"], actor=request.user)
            except ValidationError as error:
                _apply_service_errors(form, error)
            except PermissionDenied as error:
                form.add_error(None, str(error))
            else:
                messages.success(request, "Localização cadastrada.")
                return redirect("core:settings_locations")
        else:
            messages.error(request, "Corrija os campos destacados.")

    return render(
        request,
        "settings/locations.html",
        {"form": form, "locations": locations},
    )


@login_required
@require_http_methods(["GET", "POST"])
def settings_demo(request):
    if not request.user.can_manage_users:
        return HttpResponseForbidden("Somente administradores gerenciam dados de exemplo.")

    demo_loaded = ServiceOrder.objects.filter(is_demo=True).exists()
    purge_form = DemoPurgeForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "load":
            try:
                counts = load_demo_data(actor=request.user)
            except DemoDataAlreadyLoaded as error:
                messages.warning(request, str(error))
            except ValidationError as error:
                messages.error(request, "; ".join(error.messages))
            else:
                messages.success(
                    request,
                    (
                        f"Exemplos carregados: {counts.get('orders', 0)} OS, "
                        f"{counts.get('vehicles', 0)} veículos, {counts.get('clients', 0)} clientes."
                    ),
                )
                return redirect("core:settings_demo")
        elif action == "purge":
            purge_form = DemoPurgeForm(request.POST)
            if purge_form.is_valid():
                try:
                    counts = purge_demo_data(
                        actor=request.user,
                        password=purge_form.cleaned_data["password"],
                    )
                except ValidationError as error:
                    if hasattr(error, "message_dict"):
                        for field, msgs in error.message_dict.items():
                            for msg in msgs:
                                purge_form.add_error(field if field != "__all__" else None, msg)
                    else:
                        messages.error(request, "; ".join(error.messages))
                else:
                    total = sum(counts.values())
                    messages.success(request, f"Dados de exemplo removidos ({total} registros).")
                    return redirect("core:settings_demo")

    return render(
        request,
        "settings/demo.html",
        {
            "demo_loaded": demo_loaded,
            "purge_form": purge_form,
            "demo_clients": Client.objects.filter(is_demo=True).count(),
            "demo_vehicles": Vehicle.objects.filter(is_demo=True).count(),
            "demo_orders": ServiceOrder.objects.filter(is_demo=True).count(),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def settings_spreadsheets(request):
    if not request.user.can_manage_users:
        return HttpResponseForbidden("Somente administradores importam planilhas.")

    upload_form = SpreadsheetUploadForm()
    last_summary = None

    if request.method == "POST":
        upload_form = SpreadsheetUploadForm(request.POST, request.FILES)
        if upload_form.is_valid():
            try:
                last_summary = import_uploaded_file(
                    upload=upload_form.cleaned_data["arquivo"],
                    actor=request.user,
                )
            except ValueError as error:
                messages.error(request, str(error))
            except ValidationError as error:
                messages.error(request, "; ".join(error.messages))
            else:
                if last_summary.total_errors:
                    messages.warning(
                        request,
                        "Importação concluída com avisos — veja os erros abaixo.",
                    )
                else:
                    messages.success(request, "Planilha importada com sucesso.")
        else:
            messages.error(request, "Selecione um arquivo .xlsx válido.")

    return render(
        request,
        "settings/spreadsheets.html",
        {"upload_form": upload_form, "last_summary": last_summary},
    )


@login_required
@require_GET
def settings_spreadsheet_download(request):
    if not request.user.can_manage_users:
        return HttpResponseForbidden("Somente administradores exportam planilhas.")

    mode = request.GET.get("mode", "export")
    if mode not in {"template", "export"}:
        mode = "export"
    blob = build_export_workbook(mode=mode, actor=request.user)
    prefix = "Modelo" if mode == "template" else "Cadastros"
    filename = f"{prefix}_DR_Centro_{timezone.localdate().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        blob,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
