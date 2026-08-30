from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.tests import make_user
from apps.customers.models import Client
from apps.vehicles.models import Vehicle
from apps.workorders.models import Status
from apps.workorders.services import create_service_order, transition_service_order_status


class DashboardBoardTests(TestCase):
    def setUp(self):
        self.reception = make_user("recepcao", Role.RECEPTION, first_name="Ana")
        self.mechanic = make_user("mecanico", Role.MECHANIC, first_name="Carlos")
        self.owner = Client.objects.create(name="Marcos Ferreira", phone="13991234567")

        self.first = self._make_order("ABC1D23", "Chevrolet", "Onix")
        self.second = self._make_order("DEF2G45", "Volkswagen", "Gol")
        transition_service_order_status(
            self.second, new_status=Status.IN_SERVICE, user=self.mechanic
        )

    def _make_order(self, plate, brand, model, **overrides):
        vehicle = Vehicle.objects.create(
            client=self.owner, plate=plate, brand=brand, model=model
        )
        data = {
            "client": self.owner,
            "vehicle": vehicle,
            "entry_km": 50000,
            "customer_complaint": "Revisão.",
            "user": self.reception,
        }
        data.update(overrides)
        return create_service_order(**data)

    def test_dashboard_requires_login(self):
        self.assertEqual(self.client.get(reverse("dashboard:home")).status_code, 302)

    def test_board_shows_all_open_orders(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, "ABC1D23")
        self.assertContains(response, "DEF2G45")

    def test_board_has_one_column_per_board_status(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(len(response.context["columns"]), 6)

    def test_orders_land_in_the_right_column(self):
        self.client.force_login(self.reception)
        columns = {c["status"]: c for c in self.client.get(reverse("dashboard:home")).context["columns"]}
        self.assertEqual(columns[Status.WAITING_EVALUATION]["count"], 1)
        self.assertEqual(columns[Status.IN_SERVICE]["count"], 1)

    def test_summary_counts_vehicles_in_workshop(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.context["total_orders"], 2)

    def test_delivered_order_leaves_the_board(self):
        self.first.status = Status.DELIVERED
        self.first.save(update_fields=["status"])

        self.client.force_login(self.reception)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.context["total_orders"], 1)
        self.assertNotContains(response, "ABC1D23")

    def test_status_filter_narrows_the_board(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("dashboard:home"), {"status": Status.IN_SERVICE})
        self.assertEqual(response.context["total_orders"], 1)
        self.assertContains(response, "DEF2G45")

    def test_late_filter_uses_the_forecast(self):
        self.first.expected_delivery_at = timezone.now() - timedelta(hours=5)
        self.first.save(update_fields=["expected_delivery_at"])

        self.client.force_login(self.reception)
        response = self.client.get(reverse("dashboard:home"), {"late": "1"})
        self.assertEqual(response.context["total_orders"], 1)
        self.assertContains(response, "ABC1D23")

    def test_mine_filter_shows_only_the_logged_mechanic_work(self):
        self.second.mechanic = self.mechanic
        self.second.save(update_fields=["mechanic"])

        self.client.force_login(self.mechanic)
        response = self.client.get(reverse("dashboard:home"), {"mine": "1"})
        self.assertEqual(response.context["total_orders"], 1)
        self.assertContains(response, "DEF2G45")

    def test_board_partial_returns_only_the_board(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("dashboard:board"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="kanban"')
        self.assertNotContains(response, "<html")

    def test_empty_board_shows_guidance(self):
        self.first.status = Status.DELIVERED
        self.first.save(update_fields=["status"])
        self.second.status = Status.DELIVERED
        self.second.save(update_fields=["status"])

        self.client.force_login(self.reception)
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, "Nenhum veículo na oficina.")
