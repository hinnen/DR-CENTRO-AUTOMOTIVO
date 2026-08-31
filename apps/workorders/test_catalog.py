"""Cadastro rápido de mecânico e localização (select + criar)."""

from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role
from apps.accounts.services import create_mechanic_user
from apps.accounts.tests import make_user
from apps.core.models import WorkshopSettings
from apps.core.services.settings import invalidate_workshop_settings_cache
from apps.customers.models import Client
from apps.vehicles.models import Vehicle, VehicleLocation
from apps.vehicles.services import create_location
from apps.workorders.forms import mechanic_queryset


def _reset_workshop_settings():
    obj = WorkshopSettings.load()
    obj.reception_can_create_mechanic = False
    obj.save()
    invalidate_workshop_settings_cache()


class CreateMechanicServiceTests(TestCase):
    def setUp(self):
        _reset_workshop_settings()
        self.admin = make_user("admin_cat", Role.ADMIN)
        self.reception = make_user("recep_cat", Role.RECEPTION)

    def test_admin_creates_mechanic_with_four_digit_pin(self):
        user = create_mechanic_user(
            name="João Mecânico",
            username="joao_m",
            pin="4821",
            phone="13999990000",
            actor=self.admin,
        )
        self.assertEqual(user.role, Role.MECHANIC)
        self.assertTrue(user.is_active)
        self.assertIn(user, mechanic_queryset())
        self.assertEqual(authenticate(username="joao_m", password="4821"), user)

    def test_invalid_pin_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            create_mechanic_user(
                name="Teste",
                username="teste_pin",
                pin="123",
                actor=self.admin,
            )
        self.assertIn("pin", ctx.exception.message_dict)

    def test_reception_cannot_create_mechanic(self):
        with self.assertRaises(PermissionDenied):
            create_mechanic_user(
                name="Carlos",
                username="carlos_x",
                pin="9999",
                actor=self.reception,
            )


class CreateLocationServiceTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin_loc", Role.ADMIN)
        self.mechanic = make_user("mec_loc", Role.MECHANIC)

    def test_reception_path_via_admin_creates_location(self):
        location = create_location(name="Elevador 2", actor=self.admin)
        self.assertTrue(location.is_active)
        self.assertEqual(location.name, "Elevador 2")

    def test_duplicate_name_rejected(self):
        create_location(name="Pátio A", actor=self.admin)
        with self.assertRaises(ValidationError) as ctx:
            create_location(name="pátio a", actor=self.admin)
        self.assertIn("name", ctx.exception.message_dict)

    def test_mechanic_cannot_create_location(self):
        with self.assertRaises(PermissionDenied):
            create_location(name="Box 9", actor=self.mechanic)


class QuickCatalogViewTests(TestCase):
    def setUp(self):
        _reset_workshop_settings()
        self.admin = make_user("admin_view", Role.ADMIN, first_name="Admin")
        self.reception = make_user("recep_view", Role.RECEPTION, first_name="Ana")
        self.client_obj = Client.objects.create(name="Cliente Cat", phone="11999990001")
        self.vehicle = Vehicle.objects.create(
            client=self.client_obj,
            plate="CAT1A23",
            brand="VW",
            model="Gol",
            model_year=2015,
        )

    def test_admin_can_create_mechanic_via_htmx(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("workorders:quick_mechanic_create"),
            {
                "target_id": "creatable-mechanic-entry",
                "field_name": "mechanic",
                "empty_label": "Definir depois",
                "name": "Pedro Silva",
                "username": "pedro_s",
                "pin": "1357",
                "phone": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "creatable-mechanic-entry")
        self.assertContains(response, "Pedro Silva")
        self.assertContains(response, 'hx-swap-oob="outerHTML"')
        self.assertTrue(authenticate(username="pedro_s", password="1357"))

    def test_reception_gets_forbidden_on_mechanic_create(self):
        self.client.force_login(self.reception)
        response = self.client.post(
            reverse("workorders:quick_mechanic_create"),
            {
                "target_id": "x",
                "name": "X",
                "username": "x_user",
                "pin": "1111",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_reception_can_create_location_via_htmx(self):
        self.client.force_login(self.reception)
        response = self.client.post(
            reverse("workorders:quick_location_create"),
            {
                "target_id": "creatable-location-entry",
                "field_name": "location",
                "empty_label": "Definir depois",
                "name": "Rampa 3",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rampa 3")
        self.assertTrue(VehicleLocation.objects.filter(name="Rampa 3").exists())

    def test_new_entry_shows_cadastrar_for_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("workorders:new_entry"), {"vehicle": self.vehicle.uuid}
        )
        self.assertContains(response, "Cadastrar mecânico")
        self.assertContains(response, "Cadastrar localização")

    def test_new_entry_hides_mechanic_cadastrar_for_reception(self):
        self.client.force_login(self.reception)
        response = self.client.get(
            reverse("workorders:new_entry"), {"vehicle": self.vehicle.uuid}
        )
        self.assertNotContains(response, "Cadastrar mecânico")
        self.assertContains(response, "Cadastrar localização")
