"""Definições e handlers de import/export por aba."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import Role, User
from apps.accounts.services import create_operational_user, set_user_pin, split_display_name, validate_operational_pin
from apps.core.utils import normalize_phone
from apps.customers.models import Client
from apps.vehicles.models import Fuel, Vehicle, VehicleLocation, normalize_plate, validate_plate

from .common import cell_str, map_rows_by_header, parse_bool, parse_uuid

COL_ID = "id"
COL_NAME = "nome"
COL_ORDER = "ordem"
COL_ACTIVE = "ativo"

COL_PHONE = "telefone"
COL_WHATSAPP = "whatsapp"
COL_EMAIL = "email"
COL_CPF = "cpf_cnpj"
COL_NOTES = "observacoes"

COL_PLATE = "placa"
COL_CLIENT_PHONE = "cliente_telefone"
COL_BRAND = "marca"
COL_MODEL = "modelo"
COL_VERSION = "versao"
COL_MODEL_YEAR = "ano_modelo"
COL_MANUFACTURE_YEAR = "ano_fabricacao"
COL_COLOR = "cor"
COL_FUEL = "combustivel"
COL_CHASSIS = "chassi"

COL_USERNAME = "usuario"
COL_ROLE = "perfil"
COL_PIN = "pin"


def normalize_label(value: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.strip().lower()


ROLE_LABELS = {
    Role.ADMIN: "Administrador",
    Role.RECEPTION: "Recepção",
    Role.MECHANIC: "Mecânico",
}
ROLE_BY_LABEL = {normalize_label(v): k for k, v in ROLE_LABELS.items()}
FUEL_BY_LABEL = {normalize_label(label): key for key, label in Fuel.choices}


@dataclass
class SheetResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class ImportSummary:
    locations: SheetResult = field(default_factory=SheetResult)
    clients: SheetResult = field(default_factory=SheetResult)
    vehicles: SheetResult = field(default_factory=SheetResult)
    users: SheetResult = field(default_factory=SheetResult)

    @property
    def total_errors(self) -> int:
        return sum(len(r.errors) for r in (self.locations, self.clients, self.vehicles, self.users))

    def display_rows(self) -> list[tuple[str, SheetResult]]:
        return [
            ("Localizações", self.locations),
            ("Clientes", self.clients),
            ("Veículos", self.vehicles),
            ("Usuários", self.users),
        ]


SHEET_LOCATIONS = "Localizações"
SHEET_CLIENTS = "Clientes"
SHEET_VEHICLES = "Veículos"
SHEET_USERS = "Usuários"

LOCATION_HEADERS = [
    ("ID", COL_ID),
    ("Nome", COL_NAME),
    ("Ordem", COL_ORDER),
    ("Ativo", COL_ACTIVE),
]

CLIENT_HEADERS = [
    ("ID", COL_ID),
    ("Nome", COL_NAME),
    ("Telefone", COL_PHONE),
    ("WhatsApp", COL_WHATSAPP),
    ("E-mail", COL_EMAIL),
    ("CPF/CNPJ", COL_CPF),
    ("Observações", COL_NOTES),
    ("Ativo", COL_ACTIVE),
]

VEHICLE_HEADERS = [
    ("ID", COL_ID),
    ("Placa", COL_PLATE),
    ("Telefone do cliente", COL_CLIENT_PHONE),
    ("Marca", COL_BRAND),
    ("Modelo", COL_MODEL),
    ("Versão", COL_VERSION),
    ("Ano modelo", COL_MODEL_YEAR),
    ("Ano fabricação", COL_MANUFACTURE_YEAR),
    ("Cor", COL_COLOR),
    ("Combustível", COL_FUEL),
    ("Chassi", COL_CHASSIS),
    ("Observações", COL_NOTES),
    ("Ativo", COL_ACTIVE),
]

USER_HEADERS = [
    ("ID", COL_ID),
    ("Nome", COL_NAME),
    ("Usuário", COL_USERNAME),
    ("Perfil", COL_ROLE),
    ("Telefone", COL_PHONE),
    ("PIN", COL_PIN),
    ("Ativo", COL_ACTIVE),
]

LOCATION_HEADER_MAP = dict(LOCATION_HEADERS)
CLIENT_HEADER_MAP = dict(CLIENT_HEADERS)
VEHICLE_HEADER_MAP = dict(VEHICLE_HEADERS)
USER_HEADER_MAP = dict(USER_HEADERS)


def export_locations() -> list[dict[str, Any]]:
    rows = []
    for location in VehicleLocation.objects.order_by("order", "name"):
        rows.append(
            {
                COL_ID: str(location.uuid),
                COL_NAME: location.name,
                COL_ORDER: location.order,
                COL_ACTIVE: "Sim" if location.is_active else "Não",
            }
        )
    return rows


def export_clients() -> list[dict[str, Any]]:
    rows = []
    for client in Client.objects.order_by("name"):
        rows.append(
            {
                COL_ID: str(client.uuid),
                COL_NAME: client.name,
                COL_PHONE: client.phone,
                COL_WHATSAPP: client.phone_whatsapp,
                COL_EMAIL: client.email,
                COL_CPF: client.cpf_cnpj,
                COL_NOTES: client.notes,
                COL_ACTIVE: "Sim" if client.is_active else "Não",
            }
        )
    return rows


def export_vehicles() -> list[dict[str, Any]]:
    rows = []
    for vehicle in Vehicle.objects.select_related("client").order_by("plate"):
        fuel_label = dict(Fuel.choices).get(vehicle.fuel, "")
        rows.append(
            {
                COL_ID: str(vehicle.uuid),
                COL_PLATE: vehicle.plate,
                COL_CLIENT_PHONE: vehicle.client.phone,
                COL_BRAND: vehicle.brand,
                COL_MODEL: vehicle.model,
                COL_VERSION: vehicle.version,
                COL_MODEL_YEAR: vehicle.model_year or "",
                COL_MANUFACTURE_YEAR: vehicle.manufacture_year or "",
                COL_COLOR: vehicle.color,
                COL_FUEL: fuel_label,
                COL_CHASSIS: vehicle.chassis,
                COL_NOTES: vehicle.notes,
                COL_ACTIVE: "Sim" if vehicle.is_active else "Não",
            }
        )
    return rows


def export_users(*, actor) -> list[dict[str, Any]]:
    rows = []
    queryset = User.objects.order_by("first_name", "username")
    for user in queryset:
        if user.is_superuser and user.pk != actor.pk:
            continue
        rows.append(
            {
                COL_ID: str(user.uuid),
                COL_NAME: user.display_name,
                COL_USERNAME: user.username,
                COL_ROLE: ROLE_LABELS.get(user.role, user.role),
                COL_PHONE: user.phone,
                COL_PIN: "",
                COL_ACTIVE: "Sim" if user.is_active else "Não",
            }
        )
    return rows


def template_row(headers: list[tuple[str, str]]) -> dict[str, Any]:
    examples = {
        COL_ID: "",
        COL_NAME: "Exemplo — apague antes de importar",
        COL_ORDER: 0,
        COL_ACTIVE: "Sim",
        COL_PHONE: "13999999999",
        COL_WHATSAPP: "13999999999",
        COL_EMAIL: "cliente@email.com",
        COL_CPF: "",
        COL_NOTES: "Linha modelo — remova antes de enviar",
        COL_PLATE: "ABC1D23",
        COL_CLIENT_PHONE: "13999999999",
        COL_BRAND: "Volkswagen",
        COL_MODEL: "Gol",
        COL_VERSION: "1.0",
        COL_MODEL_YEAR: 2020,
        COL_MANUFACTURE_YEAR: 2019,
        COL_COLOR: "Prata",
        COL_FUEL: "Flex",
        COL_CHASSIS: "",
        COL_USERNAME: "joao_mec",
        COL_ROLE: "Mecânico",
        COL_PIN: "1234",
    }
    return {key: examples.get(key, "") for _label, key in headers}


def is_template_row(row: dict[str, Any]) -> bool:
    name = cell_str(row.get(COL_NAME)).lower()
    notes = cell_str(row.get(COL_NOTES)).lower()
    if "apague antes de importar" in name:
        return True
    if "linha modelo" in notes:
        return True
    return False


def build_export_workbook(*, mode: str, actor) -> bytes:
    from .common import build_workbook

    if mode == "template":
        sheets = [
            (SHEET_LOCATIONS, LOCATION_HEADERS, [template_row(LOCATION_HEADERS)]),
            (SHEET_CLIENTS, CLIENT_HEADERS, [template_row(CLIENT_HEADERS)]),
            (SHEET_VEHICLES, VEHICLE_HEADERS, [template_row(VEHICLE_HEADERS)]),
            (SHEET_USERS, USER_HEADERS, [template_row(USER_HEADERS)]),
        ]
    else:
        sheets = [
            (SHEET_LOCATIONS, LOCATION_HEADERS, export_locations()),
            (SHEET_CLIENTS, CLIENT_HEADERS, export_clients()),
            (SHEET_VEHICLES, VEHICLE_HEADERS, export_vehicles()),
            (SHEET_USERS, USER_HEADERS, export_users(actor=actor)),
        ]
    return build_workbook(sheets=sheets)


@transaction.atomic
def import_workbook(*, sheets: dict[str, list[dict[str, Any]]], actor) -> ImportSummary:
    if not actor.can_manage_users:
        raise ValidationError("Somente administradores importam planilhas.")

    summary = ImportSummary()
    _import_locations(sheets.get(SHEET_LOCATIONS, []), summary.locations)
    _import_clients(sheets.get(SHEET_CLIENTS, []), summary.clients)
    _import_vehicles(sheets.get(SHEET_VEHICLES, []), summary.vehicles)
    _import_users(sheets.get(SHEET_USERS, []), summary.users, actor=actor)
    return summary


def _import_locations(raw_rows: list[dict[str, Any]], result: SheetResult) -> None:
    rows = map_rows_by_header(raw_rows, LOCATION_HEADER_MAP)
    for line_no, row in enumerate(rows, start=2):
        if is_template_row(row):
            result.skipped += 1
            continue
        try:
            location = _resolve_location(row)
            name = cell_str(row.get(COL_NAME))
            if not name:
                raise ValidationError("Nome obrigatório.")
            order_raw = row.get(COL_ORDER)
            order = int(order_raw) if str(order_raw or "").strip().isdigit() else location.order if location else 0
            active = parse_bool(row.get(COL_ACTIVE), default=True)
            if location:
                location.name = name
                location.order = order
                location.is_active = bool(active)
                location.save()
                result.updated += 1
            else:
                if VehicleLocation.objects.filter(name__iexact=name).exists():
                    raise ValidationError(f"Localização «{name}» já existe.")
                VehicleLocation.objects.create(name=name, order=order, is_active=bool(active))
                result.created += 1
        except ValidationError as error:
            result.errors.append(f"Localizações linha {line_no}: {'; '.join(error.messages)}")
        except Exception as error:
            result.errors.append(f"Localizações linha {line_no}: {error}")


def _resolve_location(row: dict[str, Any]) -> VehicleLocation | None:
    item_id = parse_uuid(row.get(COL_ID))
    if item_id:
        return VehicleLocation.objects.filter(uuid=item_id).first()
    name = cell_str(row.get(COL_NAME))
    if name:
        return VehicleLocation.objects.filter(name__iexact=name).first()
    return None


def _import_clients(raw_rows: list[dict[str, Any]], result: SheetResult) -> None:
    rows = map_rows_by_header(raw_rows, CLIENT_HEADER_MAP)
    for line_no, row in enumerate(rows, start=2):
        if is_template_row(row):
            result.skipped += 1
            continue
        try:
            client = _resolve_client(row)
            name = cell_str(row.get(COL_NAME))
            phone = normalize_phone(cell_str(row.get(COL_PHONE)))
            if not name:
                raise ValidationError("Nome obrigatório.")
            if not phone:
                raise ValidationError("Telefone obrigatório.")
            whatsapp = normalize_phone(cell_str(row.get(COL_WHATSAPP))) or phone
            active = parse_bool(row.get(COL_ACTIVE), default=True)
            if client:
                client.name = name
                client.phone = phone
                client.phone_whatsapp = whatsapp
                client.email = cell_str(row.get(COL_EMAIL))
                client.cpf_cnpj = cell_str(row.get(COL_CPF))
                client.notes = cell_str(row.get(COL_NOTES))
                client.is_active = bool(active)
                client.save()
                result.updated += 1
            else:
                if Client.objects.filter(phone=phone).exists():
                    raise ValidationError(f"Telefone {phone} já cadastrado.")
                Client.objects.create(
                    name=name,
                    phone=phone,
                    phone_whatsapp=whatsapp,
                    email=cell_str(row.get(COL_EMAIL)),
                    cpf_cnpj=cell_str(row.get(COL_CPF)),
                    notes=cell_str(row.get(COL_NOTES)),
                    is_active=bool(active),
                )
                result.created += 1
        except ValidationError as error:
            result.errors.append(f"Clientes linha {line_no}: {'; '.join(error.messages)}")
        except Exception as error:
            result.errors.append(f"Clientes linha {line_no}: {error}")


def _resolve_client(row: dict[str, Any]) -> Client | None:
    item_id = parse_uuid(row.get(COL_ID))
    if item_id:
        return Client.objects.filter(uuid=item_id).first()
    phone = normalize_phone(cell_str(row.get(COL_PHONE)))
    if phone:
        return Client.objects.filter(phone=phone).first()
    return None


def _import_vehicles(raw_rows: list[dict[str, Any]], result: SheetResult) -> None:
    rows = map_rows_by_header(raw_rows, VEHICLE_HEADER_MAP)
    for line_no, row in enumerate(rows, start=2):
        if is_template_row(row):
            result.skipped += 1
            continue
        try:
            vehicle = _resolve_vehicle(row)
            plate = normalize_plate(cell_str(row.get(COL_PLATE)))
            if not plate:
                raise ValidationError("Placa obrigatória.")
            validate_plate(plate)
            client_phone = normalize_phone(cell_str(row.get(COL_CLIENT_PHONE)))
            client = Client.objects.filter(phone=client_phone).first() if client_phone else None
            if client is None and vehicle:
                client = vehicle.client
            if client is None:
                raise ValidationError("Cliente não encontrado (telefone).")
            brand = cell_str(row.get(COL_BRAND))
            model = cell_str(row.get(COL_MODEL))
            if not brand or not model:
                raise ValidationError("Marca e modelo obrigatórios.")
            fuel = _parse_fuel(row.get(COL_FUEL))
            active = parse_bool(row.get(COL_ACTIVE), default=True)
            model_year = _parse_int(row.get(COL_MODEL_YEAR))
            manufacture_year = _parse_int(row.get(COL_MANUFACTURE_YEAR))
            if vehicle:
                vehicle.client = client
                vehicle.plate = plate
                vehicle.brand = brand
                vehicle.model = model
                vehicle.version = cell_str(row.get(COL_VERSION))
                vehicle.model_year = model_year
                vehicle.manufacture_year = manufacture_year
                vehicle.color = cell_str(row.get(COL_COLOR))
                vehicle.fuel = fuel or ""
                vehicle.chassis = cell_str(row.get(COL_CHASSIS))
                vehicle.notes = cell_str(row.get(COL_NOTES))
                vehicle.is_active = bool(active)
                vehicle.save()
                result.updated += 1
            else:
                if Vehicle.objects.filter(plate=plate).exists():
                    raise ValidationError(f"Placa {plate} já cadastrada.")
                Vehicle.objects.create(
                    client=client,
                    plate=plate,
                    brand=brand,
                    model=model,
                    version=cell_str(row.get(COL_VERSION)),
                    model_year=model_year,
                    manufacture_year=manufacture_year,
                    color=cell_str(row.get(COL_COLOR)),
                    fuel=fuel or "",
                    chassis=cell_str(row.get(COL_CHASSIS)),
                    notes=cell_str(row.get(COL_NOTES)),
                    is_active=bool(active),
                )
                result.created += 1
        except ValidationError as error:
            result.errors.append(f"Veículos linha {line_no}: {'; '.join(error.messages)}")
        except Exception as error:
            result.errors.append(f"Veículos linha {line_no}: {error}")


def _resolve_vehicle(row: dict[str, Any]) -> Vehicle | None:
    item_id = parse_uuid(row.get(COL_ID))
    if item_id:
        return Vehicle.objects.filter(uuid=item_id).first()
    plate = normalize_plate(cell_str(row.get(COL_PLATE)))
    if plate:
        return Vehicle.objects.filter(plate=plate).first()
    return None


def _parse_fuel(value: Any) -> str:
    raw = cell_str(value)
    if not raw:
        return ""
    token = normalize_label(raw)
    if token in FUEL_BY_LABEL:
        return FUEL_BY_LABEL[token]
    upper = raw.upper()
    if upper in Fuel.values:
        return upper
    raise ValidationError(f"Combustível inválido: {raw}")


def _parse_int(value: Any) -> int | None:
    raw = cell_str(value)
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _import_users(raw_rows: list[dict[str, Any]], result: SheetResult, *, actor) -> None:
    rows = map_rows_by_header(raw_rows, USER_HEADER_MAP)
    for line_no, row in enumerate(rows, start=2):
        if is_template_row(row):
            result.skipped += 1
            continue
        try:
            user = _resolve_user(row)
            name = cell_str(row.get(COL_NAME))
            username = cell_str(row.get(COL_USERNAME))
            role = _parse_role(row.get(COL_ROLE))
            phone = normalize_phone(cell_str(row.get(COL_PHONE)))
            pin = cell_str(row.get(COL_PIN))
            active = parse_bool(row.get(COL_ACTIVE), default=True)
            if user:
                if user.is_superuser:
                    result.skipped += 1
                    continue
                if name:
                    first_name, last_name = split_display_name(name)
                    user.first_name = first_name
                    user.last_name = last_name
                if username and username != user.username:
                    if User.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
                        raise ValidationError(f"Usuário «{username}» já existe.")
                    user.username = username
                if role:
                    user.role = role
                    user.is_staff = role == Role.ADMIN
                user.phone = phone
                user.is_active = bool(active)
                user.save()
                if pin:
                    pin_error = validate_operational_pin(pin)
                    if pin_error:
                        raise ValidationError(pin_error)
                    set_user_pin(target=user, pin=pin, actor=actor)
                result.updated += 1
            else:
                if not name or not username or not role:
                    raise ValidationError("Nome, usuário e perfil obrigatórios para novo cadastro.")
                if not pin:
                    raise ValidationError("PIN obrigatório para novo usuário.")
                create_operational_user(
                    name=name,
                    username=username,
                    role=role,
                    pin=pin,
                    phone=phone,
                    actor=actor,
                )
                result.created += 1
        except ValidationError as error:
            result.errors.append(f"Usuários linha {line_no}: {'; '.join(error.messages)}")
        except Exception as error:
            result.errors.append(f"Usuários linha {line_no}: {error}")


def _resolve_user(row: dict[str, Any]) -> User | None:
    item_id = parse_uuid(row.get(COL_ID))
    if item_id:
        return User.objects.filter(uuid=item_id).first()
    username = cell_str(row.get(COL_USERNAME))
    if username:
        return User.objects.filter(username__iexact=username).first()
    return None


def _parse_role(value: Any) -> str:
    raw = cell_str(value)
    if not raw:
        return ""
    token = normalize_label(raw)
    if token in ROLE_BY_LABEL:
        return ROLE_BY_LABEL[token]
    upper = raw.upper()
    if upper in Role.values:
        return upper
    raise ValidationError(f"Perfil inválido: {raw}")
