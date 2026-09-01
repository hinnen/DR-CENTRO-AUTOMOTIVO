from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.tests import make_user
from apps.customers.models import Client
from apps.vehicles.models import Vehicle, VehicleLocation

from .models import OrderNumberCounter, ServiceOrder, ServiceOrderStatusHistory, Status
from .services import (
    create_service_order,
    next_order_number,
    transition_service_order_status,
    update_diagnosis,
)


class ServiceOrderFactoryMixin:
    def build_environment(self):
        self.reception = make_user("recepcao", Role.RECEPTION, first_name="Ana")
        self.mechanic = make_user("mecanico", Role.MECHANIC, first_name="Carlos")
        self.owner = Client.objects.create(name="Marcos Ferreira", phone="13991234567")
        self.vehicle = Vehicle.objects.create(
            client=self.owner, plate="ABC1D23", brand="Chevrolet", model="Onix", model_year=2020
        )

    def make_order(self, **overrides):
        data = {
            "client": self.owner,
            "vehicle": self.vehicle,
            "entry_km": 86210,
            "customer_complaint": "Barulho na dianteira.",
            "user": self.reception,
        }
        data.update(overrides)
        return create_service_order(**data)


class OrderNumberingTests(ServiceOrderFactoryMixin, TestCase):
    def setUp(self):
        self.build_environment()

    def test_first_order_is_number_one(self):
        order = self.make_order()
        self.assertEqual(order.number, 1)
        self.assertEqual(order.number_display, "OS 000001")

    def test_numbers_are_sequential_and_unique(self):
        numbers = []
        for index in range(5):
            vehicle = Vehicle.objects.create(
                client=self.owner,
                plate=f"SEQ{index}A2{index}",
                brand="Fiat",
                model="Argo",
                model_year=2021,
            )
            numbers.append(self.make_order(vehicle=vehicle).number)
        self.assertEqual(numbers, [1, 2, 3, 4, 5])
        self.assertEqual(len(set(numbers)), 5)

    def test_cancelled_order_does_not_release_its_number(self):
        first = self.make_order()
        first.status = Status.CANCELLED
        first.save(update_fields=["status"])

        second = self.make_order()
        self.assertEqual(second.number, first.number + 1)

    def test_counter_is_created_once(self):
        self.make_order()
        other = Vehicle.objects.create(
            client=self.owner, plate="CTR1A23", brand="VW", model="Polo", model_year=2019
        )
        self.make_order(vehicle=other)
        self.assertEqual(OrderNumberCounter.objects.count(), 1)
        self.assertEqual(OrderNumberCounter.objects.get().current, 2)

    def test_next_order_number_increments(self):
        self.assertEqual(next_order_number(), 1)
        self.assertEqual(next_order_number(), 2)


class ServiceOrderCreationTests(ServiceOrderFactoryMixin, TestCase):
    def setUp(self):
        self.build_environment()

    def test_new_order_starts_waiting_evaluation(self):
        order = self.make_order()
        self.assertEqual(order.status, Status.WAITING_EVALUATION)

    def test_creation_records_the_first_history_entry(self):
        order = self.make_order()
        history = order.status_history.all()
        self.assertEqual(history.count(), 1)
        self.assertEqual(history[0].previous_status, "")
        self.assertEqual(history[0].new_status, Status.WAITING_EVALUATION)
        self.assertEqual(history[0].changed_by, self.reception)

    def test_mechanic_cannot_register_entry(self):
        with self.assertRaises(PermissionDenied):
            self.make_order(user=self.mechanic)

    def test_complaint_is_required(self):
        with self.assertRaises(ValidationError):
            self.make_order(customer_complaint="   ")

    def test_negative_km_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_order(entry_km=-1)

    def test_creation_is_rolled_back_when_validation_fails(self):
        with self.assertRaises(ValidationError):
            self.make_order(customer_complaint="")
        self.assertEqual(ServiceOrder.objects.count(), 0)


class StatusTransitionTests(ServiceOrderFactoryMixin, TestCase):
    def setUp(self):
        self.build_environment()
        self.order = self.make_order()

    def test_transition_updates_status_and_history(self):
        transition_service_order_status(
            self.order, new_status=Status.IN_SERVICE, user=self.mechanic, note="Iniciado"
        )
        self.order.refresh_from_db()

        self.assertEqual(self.order.status, Status.IN_SERVICE)
        last = self.order.status_history.first()
        self.assertEqual(last.previous_status, Status.WAITING_EVALUATION)
        self.assertEqual(last.new_status, Status.IN_SERVICE)
        self.assertEqual(last.changed_by, self.mechanic)
        self.assertEqual(last.note, "Iniciado")

    def test_same_status_does_not_create_history(self):
        transition_service_order_status(
            self.order, new_status=Status.WAITING_EVALUATION, user=self.reception
        )
        self.assertEqual(self.order.status_history.count(), 1)

    def test_finishing_sets_finished_at(self):
        transition_service_order_status(self.order, new_status=Status.FINISHED, user=self.reception)
        self.order.refresh_from_db()
        self.assertIsNotNone(self.order.finished_at)

    def test_leaving_finished_clears_finished_at(self):
        transition_service_order_status(self.order, new_status=Status.FINISHED, user=self.reception)
        transition_service_order_status(self.order, new_status=Status.IN_SERVICE, user=self.reception)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.finished_at)

    def test_delivered_cannot_be_set_by_the_board(self):
        with self.assertRaises(ValidationError):
            transition_service_order_status(
                self.order, new_status=Status.DELIVERED, user=self.reception
            )

    def test_cancelled_cannot_be_set_by_the_board(self):
        with self.assertRaises(ValidationError):
            transition_service_order_status(
                self.order, new_status=Status.CANCELLED, user=self.reception
            )

    def test_closed_order_refuses_new_transitions(self):
        self.order.status = Status.DELIVERED
        self.order.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            transition_service_order_status(
                self.order, new_status=Status.IN_SERVICE, user=self.reception
            )

    def test_history_is_preserved_across_several_moves(self):
        for status in [Status.IN_EVALUATION, Status.WAITING_PART, Status.IN_SERVICE]:
            transition_service_order_status(self.order, new_status=status, user=self.mechanic)

        self.assertEqual(self.order.status_history.count(), 4)


class ServiceOrderPropertyTests(ServiceOrderFactoryMixin, TestCase):
    def setUp(self):
        self.build_environment()

    def test_is_late_only_when_open_and_past_forecast(self):
        past = timezone.now() - timedelta(hours=3)
        order = self.make_order(expected_delivery_at=past)
        self.assertTrue(order.is_late)

        order.status = Status.DELIVERED
        self.assertFalse(order.is_late)

    def test_order_without_forecast_is_never_late(self):
        self.assertFalse(self.make_order().is_late)

    def test_time_in_workshop_uses_entry_date(self):
        order = self.make_order(entry_at=timezone.now() - timedelta(days=1, hours=4))
        self.assertEqual(order.time_in_workshop, "1d 4h")

    def test_time_in_workshop_freezes_after_delivery(self):
        order = self.make_order(entry_at=timezone.now() - timedelta(days=3))
        order.delivered_at = order.entry_at + timedelta(hours=5)
        self.assertEqual(order.time_in_workshop, "5h")

    def test_time_in_status_uses_last_history_entry(self):
        order = self.make_order()
        transition_service_order_status(order, new_status=Status.IN_SERVICE, user=self.mechanic)
        order.status_history.filter(new_status=Status.IN_SERVICE).update(
            changed_at=timezone.now() - timedelta(hours=2)
        )
        self.assertEqual(order.time_in_status, "2h")

    def test_expected_delivery_display_says_today(self):
        today_at_five = timezone.localtime().replace(hour=17, minute=0, second=0, microsecond=0)
        order = self.make_order(expected_delivery_at=today_at_five)
        self.assertEqual(order.expected_delivery_display, "Hoje 17:00")

    def test_expected_delivery_display_without_forecast(self):
        self.assertEqual(self.make_order().expected_delivery_display, "—")


class DiagnosisTests(ServiceOrderFactoryMixin, TestCase):
    def setUp(self):
        self.build_environment()
        self.order = self.make_order()

    def test_mechanic_can_update_diagnosis(self):
        update_diagnosis(self.order, diagnosis="Bieletas com folga.", user=self.mechanic)
        self.order.refresh_from_db()
        self.assertEqual(self.order.diagnosis, "Bieletas com folga.")
        self.assertEqual(self.order.diagnosis_updated_by, self.mechanic)
        self.assertIsNotNone(self.order.diagnosis_updated_at)


class EntryFlowViewTests(ServiceOrderFactoryMixin, TestCase):
    def setUp(self):
        self.build_environment()
        self.location = VehicleLocation.objects.create(name="Box 1")

    def test_plate_lookup_finds_registered_vehicle(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("workorders:plate_lookup"), {"plate": "abc-1d23"})
        self.assertContains(response, "Veículo encontrado")
        self.assertContains(response, "Chevrolet Onix")

    def test_plate_lookup_offers_registration_when_missing(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("workorders:plate_lookup"), {"plate": "ZZZ9Z99"})
        self.assertContains(response, "Veículo não encontrado")
        self.assertContains(response, "Cadastrar novo veículo")

    def test_plate_lookup_old_plate_with_hyphen_finds_vehicle(self):
        from apps.vehicles.models import Vehicle

        Vehicle.objects.create(
            client=self.owner,
            plate="AFG2562",
            brand="Fiat",
            model="Uno",
        )
        self.client.force_login(self.reception)
        response = self.client.get(reverse("workorders:plate_lookup"), {"plate": "AFG-2562"})
        self.assertContains(response, "Veículo encontrado")
        self.assertContains(response, "AFG-2562")

    def test_plate_lookup_ignores_short_input(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("workorders:plate_lookup"), {"plate": "AB"})
        self.assertNotContains(response, "Veículo não encontrado")

    def test_plate_lookup_waits_for_full_plate(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("workorders:plate_lookup"), {"plate": "ABC1D2"})
        self.assertContains(response, "placa completa")
        self.assertNotContains(response, "Veículo não encontrado")

    def test_plate_lookup_hyphenated_partial_still_waits(self):
        """AFG-256 ainda tem 6 alfanuméricos — não oferece cadastro cedo demais."""
        self.client.force_login(self.reception)
        response = self.client.get(reverse("workorders:plate_lookup"), {"plate": "AFG-256"})
        self.assertContains(response, "placa completa")
        self.assertNotContains(response, "Cadastrar novo veículo")
    def test_mechanic_cannot_open_new_entry(self):
        self.client.force_login(self.mechanic)
        response = self.client.get(reverse("workorders:new_entry"))
        self.assertEqual(response.status_code, 403)

    def test_reception_creates_order_through_the_form(self):
        self.client.force_login(self.reception)
        response = self.client.post(
            reverse("workorders:new_entry"),
            {
                "vehicle": str(self.vehicle.uuid),
                "entry_km": "86210",
                "entry_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
                "customer_complaint": "Freio fazendo barulho.",
                "priority": "NORMAL",
                "location": str(self.location.pk),
            },
        )

        order = ServiceOrder.objects.get()
        self.assertRedirects(response, order.get_absolute_url())
        self.assertEqual(order.vehicle, self.vehicle)
        self.assertEqual(order.client, self.owner)
        self.assertEqual(order.created_by, self.reception)

    def test_form_errors_do_not_create_an_order(self):
        self.client.force_login(self.reception)
        response = self.client.post(
            reverse("workorders:new_entry"),
            {"vehicle": str(self.vehicle.uuid), "entry_km": "", "customer_complaint": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ServiceOrder.objects.count(), 0)

    def test_new_vehicle_creates_client_and_vehicle_together(self):
        self.client.force_login(self.reception)
        response = self.client.post(
            reverse("workorders:new_entry_vehicle"),
            {
                "plate": "XYZ9A88",
                "name": "Simone Barbosa",
                "phone": "(13) 99012-3456",
                "brand": "Toyota",
                "model": "Corolla",
            },
        )

        vehicle = Vehicle.objects.get(plate="XYZ9A88")
        self.assertRedirects(
            response, f"{reverse('workorders:new_entry')}?vehicle={vehicle.uuid}"
        )
        self.assertEqual(vehicle.client.name, "Simone Barbosa")
        self.assertEqual(vehicle.client.phone, "13990123456")

    def test_new_vehicle_can_use_existing_client(self):
        self.client.force_login(self.reception)
        response = self.client.post(
            reverse("workorders:new_entry_vehicle"),
            {
                "plate": "LMN4B77",
                "client_uuid": str(self.owner.uuid),
                "brand": "Honda",
                "model": "Civic",
            },
        )
        vehicle = Vehicle.objects.get(plate="LMN4B77")
        self.assertRedirects(
            response, f"{reverse('workorders:new_entry')}?vehicle={vehicle.uuid}"
        )
        self.assertEqual(vehicle.client, self.owner)
        self.assertEqual(self.owner.vehicles.count(), 2)


class ServiceOrderViewTests(ServiceOrderFactoryMixin, TestCase):
    def setUp(self):
        self.build_environment()
        self.order = self.make_order()

    def test_detail_requires_login(self):
        response = self.client.get(self.order.get_absolute_url())
        self.assertEqual(response.status_code, 302)

    def test_detail_shows_number_plate_and_timeline(self):
        self.client.force_login(self.mechanic)
        response = self.client.get(self.order.get_absolute_url())
        self.assertContains(response, "OS 000001")
        self.assertContains(response, "ABC1D23")
        self.assertContains(response, "Linha do tempo")

    def test_status_change_from_detail_redirects_back(self):
        self.client.force_login(self.mechanic)
        response = self.client.post(
            reverse("workorders:change_status", kwargs={"uuid": self.order.uuid}),
            {"status": Status.IN_SERVICE, "note": ""},
        )
        self.assertRedirects(response, self.order.get_absolute_url())
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Status.IN_SERVICE)

    def test_board_move_returns_json(self):
        self.client.force_login(self.mechanic)
        response = self.client.post(
            reverse("workorders:move", kwargs={"uuid": self.order.uuid}),
            {"status": Status.IN_SERVICE},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], Status.IN_SERVICE)

    def test_board_move_rejects_invalid_target_with_409(self):
        self.client.force_login(self.mechanic)
        response = self.client.post(
            reverse("workorders:move", kwargs={"uuid": self.order.uuid}),
            {"status": Status.DELIVERED},
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("error", response.json())
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Status.WAITING_EVALUATION)

    def test_board_move_requires_post(self):
        self.client.force_login(self.mechanic)
        response = self.client.get(reverse("workorders:move", kwargs={"uuid": self.order.uuid}))
        self.assertEqual(response.status_code, 405)


class WorkshopListTests(ServiceOrderFactoryMixin, TestCase):
    def setUp(self):
        self.build_environment()
        self.order = self.make_order()

    def test_open_order_appears_in_the_workshop_list(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("workorders:workshop"))
        self.assertContains(response, "ABC1D23")

    def test_delivered_order_moves_to_history(self):
        self.order.status = Status.DELIVERED
        self.order.save(update_fields=["status"])

        self.client.force_login(self.reception)
        self.assertNotContains(self.client.get(reverse("workorders:workshop")), "ABC1D23")
        self.assertContains(self.client.get(reverse("workorders:history")), "ABC1D23")

    def test_search_by_plate_filters_the_list(self):
        self.client.force_login(self.reception)
        self.assertContains(self.client.get(reverse("workorders:workshop"), {"q": "abc1d23"}), "ABC1D23")
        self.assertNotContains(
            self.client.get(reverse("workorders:workshop"), {"q": "ZZZ9Z99"}), "ABC1D23"
        )

    def test_filter_by_mechanic_without_responsible(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("workorders:workshop"), {"mechanic": "none"})
        self.assertContains(response, "ABC1D23")

    def test_late_filter_hides_orders_on_time(self):
        self.order.expected_delivery_at = timezone.now() + timedelta(days=1)
        self.order.save(update_fields=["expected_delivery_at"])

        self.client.force_login(self.reception)
        response = self.client.get(reverse("workorders:workshop"), {"late": "1"})
        self.assertNotContains(response, "ABC1D23")


class HistoryIntegrityTests(ServiceOrderFactoryMixin, TestCase):
    def setUp(self):
        self.build_environment()

    def test_history_survives_status_round_trip(self):
        order = self.make_order()
        sequence = [Status.IN_EVALUATION, Status.WAITING_PART, Status.IN_EVALUATION, Status.IN_SERVICE]
        for status in sequence:
            transition_service_order_status(order, new_status=status, user=self.mechanic)

        recorded = list(
            ServiceOrderStatusHistory.objects.filter(service_order=order)
            .order_by("id")
            .values_list("new_status", flat=True)
        )
        self.assertEqual(recorded, [Status.WAITING_EVALUATION, *sequence])
