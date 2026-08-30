"""Popula o banco com um dia típico de oficina, para testar sem digitar nada."""

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.customers.models import Client
from apps.vehicles.models import Fuel, Vehicle, VehicleLocation
from apps.workorders.models import (
    DEFAULT_INSPECTION_ITEMS,
    FuelLevel,
    Inspection,
    InspectionItem,
    ItemCondition,
    Priority,
    ServiceOrderStatusHistory,
    ServiceTask,
    Status,
    TaskStatus,
)
from apps.workorders.services import create_service_order, transition_service_order_status

User = get_user_model()

LOCATIONS = ["Box 1", "Box 2", "Box 3", "Elevador 1", "Elevador 2", "Pátio", "Estacionamento"]

USERS = [
    ("admin", "Renan Hinnen", Role.ADMIN),
    ("recepcao", "Ana Paula Souza", Role.RECEPTION),
    ("mecanico1", "Carlos Eduardo Lima", Role.MECHANIC),
    ("mecanico2", "Jorge Nascimento", Role.MECHANIC),
    ("mecanico3", "Wesley Ramos", Role.MECHANIC),
]

CLIENTS = [
    ("Marcos Antônio Ferreira", "13991234567"),
    ("Juliana Prado", "13992345678"),
    ("Roberto Carlos Menezes", "13993456789"),
    ("Fernanda Lopes", "13994567890"),
    ("Paulo Henrique Dias", "13995678901"),
    ("Camila Rodrigues", "13996789012"),
    ("Anderson Silva", "13997890123"),
    ("Patrícia Gomes", "13998901234"),
    ("Eduardo Tavares", "13999012345"),
    ("Simone Barbosa", "13990123456"),
    ("Transportadora Litoral Ltda", "1332215588"),
    ("Padaria Pão Quente ME", "1332216677"),
]

VEHICLES = [
    ("ABC1D23", "Chevrolet", "Onix", "LT 1.0", 2020, "Prata", Fuel.FLEX),
    ("DEF2G45", "Volkswagen", "Gol", "1.6 MSI", 2018, "Branco", Fuel.FLEX),
    ("GHI3J67", "Fiat", "Argo", "Drive 1.3", 2021, "Vermelho", Fuel.FLEX),
    ("JKL4M89", "Hyundai", "HB20", "Comfort 1.0", 2019, "Preto", Fuel.FLEX),
    ("MNO5P01", "Toyota", "Corolla", "XEi 2.0", 2022, "Prata", Fuel.FLEX),
    ("PQR6S23", "Honda", "Civic", "EXL 2.0", 2017, "Cinza", Fuel.FLEX),
    ("STU7V45", "Renault", "Kwid", "Zen 1.0", 2021, "Azul", Fuel.FLEX),
    ("VWX8Y67", "Jeep", "Renegade", "Longitude 1.8", 2020, "Branco", Fuel.FLEX),
    ("ABC1234", "Ford", "Ka", "SE 1.0", 2016, "Prata", Fuel.FLEX),
    ("DEF5678", "Chevrolet", "S10", "LTZ 2.8", 2019, "Preto", Fuel.DIESEL),
    ("GHI9012", "Volkswagen", "Saveiro", "Robust 1.6", 2020, "Branco", Fuel.FLEX),
    ("JKL3456", "Fiat", "Strada", "Freedom 1.3", 2022, "Vermelho", Fuel.FLEX),
    ("MNO7890", "Nissan", "Kicks", "SV 1.6", 2021, "Cinza", Fuel.FLEX),
    ("PQR1234", "Peugeot", "208", "Active 1.6", 2018, "Azul", Fuel.FLEX),
    ("STU5678", "Citroën", "C3", "Feel 1.6", 2017, "Prata", Fuel.FLEX),
    ("VWX9012", "Mercedes-Benz", "Sprinter", "415 Furgão", 2019, "Branco", Fuel.DIESEL),
]

COMPLAINTS = [
    "Barulho na dianteira ao passar em lombada.",
    "Motor falhando em marcha lenta e luz de injeção acesa.",
    "Ar-condicionado não gela.",
    "Revisão dos 40.000 km.",
    "Freio fazendo barulho e pedal baixo.",
    "Carro puxando para a direita e pneu gastando irregular.",
    "Troca de óleo e filtros.",
    "Embreagem patinando em subida.",
    "Vazamento de óleo embaixo do motor.",
    "Bateria descarregando durante a noite.",
    "Direção hidráulica pesada e barulhenta.",
    "Suspensão traseira batendo em buraco.",
]

DIAGNOSES = [
    "Bieletas da barra estabilizadora com folga. Recomendada a troca do par.",
    "Bobina de ignição do cilindro 3 com falha intermitente.",
    "Sistema com pouco gás. Identificado vazamento na válvula de serviço.",
    "Pastilhas dianteiras no limite e disco empenado.",
    "Alinhamento fora de especificação e amortecedor dianteiro direito com vazamento.",
    "Retentor do cárter ressecado.",
]

TASKS = [
    "Trocar óleo e filtro",
    "Substituir bieletas dianteiras",
    "Alinhamento e balanceamento",
    "Trocar pastilhas de freio",
    "Retificar discos dianteiros",
    "Substituir bobina de ignição",
    "Higienizar e recarregar o ar-condicionado",
    "Verificar barulho na suspensão",
    "Trocar correia dentada",
    "Revisar sistema elétrico",
    "Substituir amortecedor dianteiro",
    "Trocar filtro de combustível",
]


class Command(BaseCommand):
    help = "Cria usuários, clientes, veículos e ordens de serviço de demonstração."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Apaga os dados operacionais antes de criar os novos.",
        )
        parser.add_argument(
            "--password",
            default="oficina123",
            help="Senha usada nos usuários de demonstração.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from django.conf import settings

        if not settings.DEBUG:
            self.stderr.write(
                self.style.ERROR(
                    "seed_demo recusado: DEBUG=False. "
                    "Não rode seed em produção (cria admin/oficina123 e pode apagar dados)."
                )
            )
            return

        random.seed(42)
        password = options["password"]

        if options["reset"]:
            self.stdout.write("Apagando dados operacionais…")
            from apps.workorders.models import OrderNumberCounter, ServiceOrder

            # As demais tabelas caem junto pela cascata da OS.
            ServiceOrderStatusHistory.objects.all().delete()
            ServiceOrder.objects.all().delete()
            OrderNumberCounter.objects.all().delete()
            Vehicle.objects.all().delete()
            Client.objects.all().delete()

        users = self._create_users(password)
        locations = self._create_locations()
        clients = self._create_clients()
        vehicles = self._create_vehicles(clients)
        self._create_orders(users, locations, vehicles)

        self.stdout.write(self.style.SUCCESS("\nDados de demonstração criados."))
        self.stdout.write(f"Usuários (senha: {password}):")
        for username, name, role in USERS:
            self.stdout.write(f"  {username:<12} {name:<24} {role.label}")

    # ------------------------------------------------------------------

    def _create_users(self, password):
        users = {}
        for username, full_name, role in USERS:
            first, _, last = full_name.partition(" ")
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": role,
                    "email": f"{username}@oficina.local",
                    "is_staff": role == Role.ADMIN,
                    "is_superuser": role == Role.ADMIN,
                },
            )
            if created:
                user.set_password(password)
                user.save()
            users[username] = user

        self.stdout.write(f"Usuários: {len(users)}")
        return users

    def _create_locations(self):
        locations = []
        for index, name in enumerate(LOCATIONS):
            location, _ = VehicleLocation.objects.get_or_create(
                name=name, defaults={"order": index}
            )
            locations.append(location)

        self.stdout.write(f"Localizações: {len(locations)}")
        return locations

    def _create_clients(self):
        clients = []
        for name, phone in CLIENTS:
            client, _ = Client.objects.get_or_create(
                phone=phone, defaults={"name": name, "phone_whatsapp": phone}
            )
            clients.append(client)

        self.stdout.write(f"Clientes: {len(clients)}")
        return clients

    def _create_vehicles(self, clients):
        vehicles = []
        for index, (plate, brand, model, version, year, color, fuel) in enumerate(VEHICLES):
            vehicle, _ = Vehicle.objects.get_or_create(
                plate=plate,
                defaults={
                    "client": clients[index % len(clients)],
                    "brand": brand,
                    "model": model,
                    "version": version,
                    "model_year": year,
                    "manufacture_year": year - 1,
                    "color": color,
                    "fuel": fuel,
                },
            )
            vehicles.append(vehicle)

        self.stdout.write(f"Veículos: {len(vehicles)}")
        return vehicles

    def _create_orders(self, users, locations, vehicles):
        admin = users["admin"]
        mechanics = [users["mecanico1"], users["mecanico2"], users["mecanico3"]]
        now = timezone.now()

        # Distribuição pensada para o Kanban não nascer vazio nem uniforme.
        plan = [
            (Status.WAITING_EVALUATION, 3),
            (Status.IN_EVALUATION, 2),
            (Status.WAITING_APPROVAL, 2),
            (Status.WAITING_PART, 2),
            (Status.IN_SERVICE, 3),
            (Status.FINISHED, 2),
            (Status.DELIVERED, 2),
        ]

        vehicle_pool = list(vehicles)
        random.shuffle(vehicle_pool)
        index = 0
        created = 0

        for status, quantity in plan:
            for _ in range(quantity):
                vehicle = vehicle_pool[index % len(vehicle_pool)]
                index += 1

                hours_ago = random.randint(2, 96)
                entry_at = now - timedelta(hours=hours_ago)

                # Um terço dos casos nasce atrasado, para exercitar o alerta.
                if random.random() < 0.33:
                    expected = now - timedelta(hours=random.randint(1, 20))
                else:
                    expected = now + timedelta(hours=random.randint(3, 60))

                order = create_service_order(
                    client=vehicle.client,
                    vehicle=vehicle,
                    entry_km=random.randint(18_000, 145_000),
                    customer_complaint=random.choice(COMPLAINTS),
                    user=admin,
                    entry_at=entry_at,
                    mechanic=random.choice(mechanics) if status != Status.WAITING_EVALUATION else None,
                    expected_delivery_at=expected,
                    location=random.choice(locations),
                    priority=random.choices(
                        [Priority.NORMAL, Priority.HIGH, Priority.URGENT], weights=[7, 2, 1]
                    )[0],
                )

                self._create_tasks(order, entry_at)
                self._create_inspection(order, admin, entry_at)
                self._advance_to(order, status, admin, entry_at)
                created += 1

        self.stdout.write(f"Ordens de serviço: {created}")

    def _create_tasks(self, order, entry_at):
        """Dois a quatro serviços por OS, parte deles já concluída."""
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

    def _create_inspection(self, order, user, entry_at):
        """Vistoria de entrada em parte das OS, com algumas avarias."""
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
                    note="Risco na porta traseira esquerda." if condition == ItemCondition.DAMAGE else "",
                )
                for position, ((key, label), condition) in enumerate(
                    zip(DEFAULT_INSPECTION_ITEMS, conditions), start=1
                )
            ]
        )

    def _advance_to(self, order, target_status, user, entry_at):
        """Leva a OS até o status desejado passando pelos intermediários."""
        path = {
            Status.WAITING_EVALUATION: [],
            Status.IN_EVALUATION: [Status.IN_EVALUATION],
            Status.WAITING_APPROVAL: [Status.IN_EVALUATION, Status.WAITING_APPROVAL],
            Status.WAITING_PART: [Status.IN_EVALUATION, Status.WAITING_PART],
            Status.IN_SERVICE: [Status.IN_EVALUATION, Status.IN_SERVICE],
            Status.FINISHED: [Status.IN_EVALUATION, Status.IN_SERVICE, Status.FINISHED],
            Status.DELIVERED: [Status.IN_EVALUATION, Status.IN_SERVICE, Status.FINISHED],
        }[target_status]

        step = timedelta(hours=2)
        moment = entry_at

        for status in path:
            moment += step
            transition_service_order_status(order, new_status=status, user=user)
            # O histórico usa "agora" por padrão; a demonstração precisa de datas
            # coerentes com a entrada para os tempos fazerem sentido na tela.
            order.status_history.filter(new_status=status).update(changed_at=moment)

        if path and order.status in (Status.IN_EVALUATION, Status.IN_SERVICE, Status.WAITING_APPROVAL):
            order.diagnosis = random.choice(DIAGNOSES)
            order.diagnosis_updated_at = moment
            order.diagnosis_updated_by = user
            order.save(update_fields=["diagnosis", "diagnosis_updated_at", "diagnosis_updated_by"])

        if target_status == Status.DELIVERED:
            delivered_at = moment + step
            order.status = Status.DELIVERED
            order.finished_at = moment
            order.delivered_at = delivered_at
            order.delivered_by = user
            order.exit_km = order.entry_km + random.randint(1, 40)
            # Uma das entregas sai com terceiro registrado, para a tela mostrar
            # como o campo aparece quando não é o dono que busca o carro.
            if random.random() < 0.5:
                order.received_by_name = random.choice(
                    ["Marcos Ferreira (filho)", "Juliana Prado (esposa)", "Carlos - motorista"]
                )
            order.save()
            ServiceOrderStatusHistory.objects.create(
                service_order=order,
                previous_status=Status.FINISHED,
                new_status=Status.DELIVERED,
                changed_by=user,
                changed_at=delivered_at,
                note="Veículo entregue ao cliente",
            )
