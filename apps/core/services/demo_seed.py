"""Carrega dados de demonstração (clientes, veículos, OS em vários status)."""

from __future__ import annotations

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.services import create_operational_user
from apps.core.management.commands.seed_demo import (
    CLIENTS,
    COMPLAINTS,
    DIAGNOSES,
    LOCATIONS,
    TASKS,
    VEHICLES,
)
from apps.customers.models import Client
from apps.vehicles.models import Fuel, Vehicle, VehicleLocation
from apps.workorders.models import (
    DEFAULT_INSPECTION_ITEMS,
    FuelLevel,
    Inspection,
    InspectionItem,
    ItemCondition,
    Priority,
    ServiceOrder,
    ServiceTask,
    Status,
    TaskStatus,
)
from apps.workorders.services import create_service_order, transition_service_order_status

User = get_user_model()

DEMO_MECHANICS = [
    ("demo_mec1", "Carlos Demo", "4821"),
    ("demo_mec2", "Jorge Demo", "5932"),
    ("demo_mec3", "Wesley Demo", "6043"),
]

STATUS_PLAN = [
    (Status.WAITING_EVALUATION, 3),
    (Status.IN_EVALUATION, 2),
    (Status.WAITING_APPROVAL, 2),
    (Status.WAITING_PART, 2),
    (Status.IN_SERVICE, 3),
    (Status.FINISHED, 2),
]


class DemoDataAlreadyLoaded(Exception):
    """Exemplos já existem no banco."""


@transaction.atomic
def load_demo_data(*, actor) -> dict[str, int]:
    """Popula clientes, veículos e OS de exemplo marcados com is_demo=True."""
    if ServiceOrder.objects.filter(is_demo=True).exists():
        raise DemoDataAlreadyLoaded("Já existem dados de exemplo. Limpe antes de recarregar.")

    random.seed(42)
    counts: dict[str, int] = {}

    locations = _ensure_locations()
    counts["locations"] = len(locations)

    clients = _create_demo_clients()
    counts["clients"] = len(clients)

    vehicles = _create_demo_vehicles(clients)
    counts["vehicles"] = len(vehicles)

    mechanics = _ensure_demo_mechanics(actor)
    counts["mechanics"] = len(mechanics)

    counts["orders"] = _create_demo_orders(actor, mechanics, locations, vehicles)
    return counts


def _ensure_locations() -> list[VehicleLocation]:
    locations = []
    for index, name in enumerate(LOCATIONS):
        location, created = VehicleLocation.objects.get_or_create(
            name=name, defaults={"order": index, "is_demo": True}
        )
        if created:
            locations.append(location)
        elif location.is_demo:
            locations.append(location)
        else:
            locations.append(location)
    return locations


def _create_demo_clients() -> list[Client]:
    clients = []
    for name, phone in CLIENTS:
        client = Client.objects.filter(phone=phone).first()
        if client:
            if client.is_demo:
                clients.append(client)
            continue
        client = Client.objects.create(
            name=name,
            phone=phone,
            phone_whatsapp=phone,
            is_demo=True,
        )
        clients.append(client)
    if len(clients) < 3:
        raise DemoDataAlreadyLoaded(
            "Não foi possível criar clientes de exemplo (telefones já usados por cadastros reais)."
        )
    return clients


def _create_demo_vehicles(clients: list[Client]) -> list[Vehicle]:
    vehicles = []
    for index, (plate, brand, model, version, year, color, fuel) in enumerate(VEHICLES):
        vehicle = Vehicle.objects.filter(plate=plate).first()
        if vehicle:
            if vehicle.is_demo:
                vehicles.append(vehicle)
            continue
        vehicle = Vehicle.objects.create(
            client=clients[index % len(clients)],
            plate=plate,
            brand=brand,
            model=model,
            version=version,
            model_year=year,
            manufacture_year=year - 1,
            color=color,
            fuel=fuel,
            is_demo=True,
        )
        vehicles.append(vehicle)
    if len(vehicles) < 5:
        raise DemoDataAlreadyLoaded(
            "Não foi possível criar veículos de exemplo (placas já usadas por cadastros reais)."
        )
    return vehicles


def _ensure_demo_mechanics(actor) -> list[User]:
    demo_mechanics = list(User.objects.filter(role=Role.MECHANIC, is_active=True, is_demo=True)[:3])
    if len(demo_mechanics) >= 2:
        return demo_mechanics

    mechanics = list(demo_mechanics)
    for username, name, pin in DEMO_MECHANICS:
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            if user.is_demo:
                mechanics.append(user)
            continue
        user = create_operational_user(
            name=name,
            username=username,
            role=Role.MECHANIC,
            pin=pin,
            actor=actor,
        )
        user.is_demo = True
        user.save(update_fields=["is_demo"])
        mechanics.append(user)
        if len(mechanics) >= 3:
            break

    existing = list(User.objects.filter(role=Role.MECHANIC, is_active=True)[:3])
    pool = mechanics or existing
    if len(pool) < 1:
        raise DemoDataAlreadyLoaded("Cadastre ao menos um mecânico antes de carregar exemplos.")
    return pool[:3]


def _create_demo_orders(actor, mechanics, locations, vehicles) -> int:
    now = timezone.now()
    pool = list(vehicles)
    random.shuffle(pool)
    index = 0
    created = 0

    for status, quantity in STATUS_PLAN:
        for _ in range(quantity):
            vehicle = pool[index % len(pool)]
            index += 1
            if ServiceOrder.objects.filter(vehicle=vehicle, status__in=Status.values).exists():
                open_order = vehicle.service_orders.exclude(
                    status__in=[Status.DELIVERED, Status.CANCELLED]
                ).first()
                if open_order:
                    continue

            hours_ago = random.randint(2, 96)
            entry_at = now - timedelta(hours=hours_ago)
            expected = (
                now - timedelta(hours=random.randint(1, 20))
                if random.random() < 0.33
                else now + timedelta(hours=random.randint(3, 60))
            )

            order = create_service_order(
                client=vehicle.client,
                vehicle=vehicle,
                entry_km=random.randint(18_000, 145_000),
                customer_complaint=random.choice(COMPLAINTS),
                user=actor,
                entry_at=entry_at,
                mechanic=random.choice(mechanics) if status != Status.WAITING_EVALUATION else None,
                expected_delivery_at=expected,
                location=random.choice(locations),
                priority=random.choices(
                    [Priority.NORMAL, Priority.HIGH, Priority.URGENT], weights=[7, 2, 1]
                )[0],
            )
            order.is_demo = True
            order.save(update_fields=["is_demo"])

            _create_tasks(order, entry_at, mechanics)
            _maybe_inspection(order, actor, entry_at)
            _advance_to(order, status, actor, entry_at)
            if status in {Status.FINISHED} and random.random() < 0.5:
                order.diagnosis = random.choice(DIAGNOSES)
                order.save(update_fields=["diagnosis"])
            created += 1
    return created


def _create_tasks(order, entry_at, mechanics):
    for position, title in enumerate(random.sample(TASKS, random.randint(2, 4)), start=1):
        done = random.random() < 0.45
        ServiceTask.objects.create(
            service_order=order,
            title=title,
            position=position,
            status=TaskStatus.DONE if done else TaskStatus.PENDING,
            mechanic=order.mechanic if done else None,
            started_at=entry_at + timedelta(hours=position) if done else None,
            completed_at=entry_at + timedelta(hours=position + 1) if done else None,
        )


def _maybe_inspection(order, user, entry_at):
    if random.random() < 0.4:
        return
    inspection = Inspection.objects.create(
        service_order=order,
        performed_by=user,
        performed_at=entry_at,
        fuel_level=random.choice(
            [FuelLevel.RESERVE, FuelLevel.QUARTER, FuelLevel.HALF, FuelLevel.THREE_QUARTERS]
        ),
    )
    conditions = random.choices(
        [ItemCondition.OK, ItemCondition.ATTENTION, ItemCondition.DAMAGE, ItemCondition.NOT_CHECKED],
        weights=[70, 12, 8, 10],
        k=len(DEFAULT_INSPECTION_ITEMS),
    )
    InspectionItem.objects.bulk_create(
        [
            InspectionItem(
                inspection=inspection,
                key=key,
                label=label,
                condition=condition,
                position=position,
            )
            for position, ((key, label), condition) in enumerate(
                zip(DEFAULT_INSPECTION_ITEMS, conditions), start=1
            )
        ]
    )


def _advance_to(order, target_status, user, entry_at):
    path_map = {
        Status.WAITING_EVALUATION: [],
        Status.IN_EVALUATION: [Status.IN_EVALUATION],
        Status.WAITING_APPROVAL: [Status.IN_EVALUATION, Status.WAITING_APPROVAL],
        Status.WAITING_PART: [Status.IN_EVALUATION, Status.WAITING_PART],
        Status.IN_SERVICE: [Status.IN_EVALUATION, Status.IN_SERVICE],
        Status.FINISHED: [Status.IN_EVALUATION, Status.IN_SERVICE, Status.FINISHED],
    }
    for status in path_map[target_status]:
        transition_service_order_status(order, new_status=status, user=user)
