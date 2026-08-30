"""Testes das operações de serviços, fotos, vistoria, saída e cancelamento.

Ficam separados de ``tests.py`` (numeração, status e entrada) para que cada
arquivo continue legível conforme o sistema cresce.
"""

import base64
import io
import shutil
import tempfile
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.accounts.models import Role
from apps.accounts.tests import make_user
from apps.customers.models import Client
from apps.vehicles.models import Vehicle

from .forms import DeliveryForm
from .models import (
    ActivityLog,
    EventType,
    ItemCondition,
    PhotoCategory,
    ServiceOrderPhoto,
    Status,
    TaskStatus,
)
from .services import (
    add_photos,
    add_service_task,
    cancel_service_order,
    complete_service_task,
    create_service_order,
    deliver_vehicle,
    finalize_service_order,
    get_or_build_inspection,
    remove_photo,
    save_inspection,
    transition_service_order_status,
)

MEDIA_ROOT = tempfile.mkdtemp(prefix="dr-test-media-")


def make_image(name="foto.jpg", fmt="JPEG", content_type="image/jpeg", size=(40, 30)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (163, 27, 51)).save(buffer, format=fmt)
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type=content_type)


class OperationsMixin:
    def build_environment(self):
        self.admin = make_user("admin", Role.ADMIN, first_name="Renan")
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


# ---------------------------------------------------------------------------
# Serviços
# ---------------------------------------------------------------------------


class ServiceTaskTests(OperationsMixin, TestCase):
    def setUp(self):
        self.build_environment()
        self.order = self.make_order()

    def test_tasks_are_numbered_in_the_order_they_are_added(self):
        first = add_service_task(self.order, title="Trocar óleo", user=self.reception)
        second = add_service_task(self.order, title="Alinhar", user=self.reception)
        self.assertEqual([first.position, second.position], [1, 2])

    def test_title_is_required(self):
        with self.assertRaises(ValidationError):
            add_service_task(self.order, title="   ", user=self.reception)

    def test_progress_counts_only_open_and_done_tasks(self):
        add_service_task(self.order, title="Trocar óleo", user=self.reception)
        second = add_service_task(self.order, title="Alinhar", user=self.reception)
        complete_service_task(second, user=self.mechanic)

        progress = self.order.task_progress
        self.assertEqual((progress["done"], progress["total"]), (1, 2))
        self.assertFalse(progress["all_done"])

    def test_cancelled_task_leaves_the_progress_denominator(self):
        add_service_task(self.order, title="Trocar óleo", user=self.reception)
        cancelled = add_service_task(self.order, title="Alinhar", user=self.reception)
        from .services import cancel_service_task

        cancel_service_task(cancelled, user=self.reception)

        progress = self.order.task_progress
        self.assertEqual(progress["total"], 1)

    def test_completing_assigns_the_mechanic_who_did_it(self):
        task = add_service_task(self.order, title="Trocar óleo", user=self.reception)
        complete_service_task(task, user=self.mechanic, performed_service="Óleo 5W30 trocado.")

        task.refresh_from_db()
        self.assertEqual(task.status, TaskStatus.DONE)
        self.assertEqual(task.mechanic, self.mechanic)
        self.assertIsNotNone(task.completed_at)
        self.assertIn("5W30", task.performed_service)

    def test_closed_order_does_not_accept_new_tasks(self):
        deliver_vehicle(self.order, user=self.reception, exit_km=86300)
        with self.assertRaises(ValidationError):
            add_service_task(self.order, title="Trocar óleo", user=self.reception)

    def test_completing_a_task_is_audited(self):
        task = add_service_task(self.order, title="Trocar óleo", user=self.reception)
        complete_service_task(task, user=self.mechanic)

        self.assertTrue(
            self.order.activities.filter(event_type=EventType.TASK_COMPLETED).exists()
        )


# ---------------------------------------------------------------------------
# Fotos
# ---------------------------------------------------------------------------


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class PhotoTests(OperationsMixin, TestCase):
    def setUp(self):
        self.build_environment()
        self.order = self.make_order()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_photos_are_attached_to_the_order_and_to_the_vehicle(self):
        photos = add_photos(
            self.order,
            images=[make_image()],
            category=PhotoCategory.ENTRY,
            user=self.reception,
        )
        photo = photos[0]
        self.assertEqual(photo.vehicle, self.vehicle)
        self.assertEqual(photo.uploaded_by, self.reception)

    def test_invalid_category_is_rejected(self):
        with self.assertRaises(ValidationError):
            add_photos(self.order, images=[make_image()], category="QUALQUER", user=self.reception)

    def test_removal_is_logical_and_keeps_who_removed_it(self):
        photo = add_photos(
            self.order, images=[make_image()], category=PhotoCategory.ENTRY, user=self.reception
        )[0]
        remove_photo(photo, user=self.admin)

        photo.refresh_from_db()
        self.assertTrue(photo.is_deleted)
        self.assertEqual(photo.deleted_by, self.admin)
        self.assertTrue(ServiceOrderPhoto.objects.filter(pk=photo.pk).exists())
        self.assertFalse(ServiceOrderPhoto.objects.visible().filter(pk=photo.pk).exists())

    def test_mechanic_cannot_remove_a_photo(self):
        photo = add_photos(
            self.order, images=[make_image()], category=PhotoCategory.ENTRY, user=self.reception
        )[0]
        with self.assertRaises(PermissionDenied):
            remove_photo(photo, user=self.mechanic)

    def test_upload_rejects_a_file_that_is_not_an_image(self):
        self.client.force_login(self.reception)
        fake = SimpleUploadedFile("virus.jpg", b"MZ\x90\x00 not an image", content_type="image/jpeg")

        response = self.client.post(
            reverse("workorders:upload_photos", args=[self.order.uuid]),
            {"images": fake, "category": PhotoCategory.ENTRY},
            follow=True,
        )

        self.assertEqual(self.order.photos.count(), 0)
        self.assertContains(response, "não pôde ser lido como imagem")

    def test_upload_rejects_a_disallowed_extension(self):
        self.client.force_login(self.reception)
        gif = make_image(name="foto.gif", fmt="GIF", content_type="image/gif")

        self.client.post(
            reverse("workorders:upload_photos", args=[self.order.uuid]),
            {"images": gif, "category": PhotoCategory.ENTRY},
        )
        self.assertEqual(self.order.photos.count(), 0)

    def test_upload_accepts_several_photos_at_once(self):
        self.client.force_login(self.reception)
        self.client.post(
            reverse("workorders:upload_photos", args=[self.order.uuid]),
            {
                "images": [make_image("a.jpg"), make_image("b.png", fmt="PNG", content_type="image/png")],
                "category": PhotoCategory.ENTRY,
            },
        )
        self.assertEqual(self.order.photos.visible().count(), 2)


# ---------------------------------------------------------------------------
# Vistoria
# ---------------------------------------------------------------------------


class InspectionTests(OperationsMixin, TestCase):
    def setUp(self):
        self.build_environment()
        self.order = self.make_order()

    def test_checklist_is_created_with_the_default_items(self):
        inspection = get_or_build_inspection(self.order)
        self.assertEqual(inspection.items.count(), 12)
        self.assertTrue(
            all(item.condition == ItemCondition.NOT_CHECKED for item in inspection.items.all())
        )

    def test_building_twice_does_not_duplicate_the_checklist(self):
        first = get_or_build_inspection(self.order)
        self.order.refresh_from_db()
        second = get_or_build_inspection(self.order)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(second.items.count(), 12)

    def test_saving_records_conditions_notes_and_author(self):
        inspection = get_or_build_inspection(self.order)
        keys = list(inspection.items.values_list("key", flat=True))

        save_inspection(
            self.order,
            conditions={keys[0]: ItemCondition.DAMAGE, keys[1]: ItemCondition.OK},
            notes_by_key={keys[0]: "Risco na porta."},
            fuel_level="1_2",
            notes="Cliente deixou documentos no porta-luvas.",
            user=self.reception,
        )

        inspection.refresh_from_db()
        first = inspection.items.get(key=keys[0])
        self.assertEqual(first.condition, ItemCondition.DAMAGE)
        self.assertEqual(first.note, "Risco na porta.")
        self.assertEqual(inspection.performed_by, self.reception)
        self.assertEqual(inspection.summary["damage"], 1)

    def test_saving_is_audited(self):
        get_or_build_inspection(self.order)
        save_inspection(
            self.order,
            conditions={},
            notes_by_key={},
            fuel_level="CHEIO",
            notes="",
            user=self.reception,
        )
        self.assertTrue(
            self.order.activities.filter(event_type=EventType.INSPECTION_SAVED).exists()
        )


# ---------------------------------------------------------------------------
# Finalização, saída e cancelamento
# ---------------------------------------------------------------------------


class DeliveryTests(OperationsMixin, TestCase):
    def setUp(self):
        self.build_environment()
        self.order = self.make_order()

    def test_finalizing_keeps_the_vehicle_in_the_workshop(self):
        finalize_service_order(self.order, user=self.reception)
        self.order.refresh_from_db()

        self.assertEqual(self.order.status, Status.FINISHED)
        self.assertIsNotNone(self.order.finished_at)
        self.assertIsNone(self.order.delivered_at)
        self.assertTrue(self.order.is_open)

    def test_delivering_closes_the_order_and_records_who_delivered(self):
        deliver_vehicle(self.order, user=self.reception, exit_km=86300, exit_notes="Tudo certo.")
        self.order.refresh_from_db()

        self.assertEqual(self.order.status, Status.DELIVERED)
        self.assertEqual(self.order.delivered_by, self.reception)
        self.assertEqual(self.order.exit_km, 86300)
        self.assertEqual(self.order.km_driven, 90)
        self.assertIsNotNone(self.order.delivered_at)
        self.assertIsNotNone(self.order.finished_at)

    def test_delivered_vehicle_leaves_the_board(self):
        from .models import ServiceOrder

        deliver_vehicle(self.order, user=self.reception, exit_km=86300)
        self.assertFalse(ServiceOrder.objects.on_board().filter(pk=self.order.pk).exists())
        self.assertTrue(ServiceOrder.objects.closed().filter(pk=self.order.pk).exists())

    def test_lower_exit_km_requires_a_justification(self):
        with self.assertRaises(ValidationError) as ctx:
            deliver_vehicle(self.order, user=self.reception, exit_km=80000)
        self.assertIn("exit_km_justification", ctx.exception.message_dict)

    def test_lower_exit_km_is_accepted_with_a_justification(self):
        deliver_vehicle(
            self.order,
            user=self.reception,
            exit_km=80000,
            exit_km_justification="Painel trocado durante o serviço.",
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.exit_km, 80000)
        self.assertIn("Painel trocado", self.order.exit_km_justification)

    def test_justification_is_not_kept_when_the_km_is_normal(self):
        deliver_vehicle(
            self.order,
            user=self.reception,
            exit_km=86300,
            exit_km_justification="texto irrelevante",
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.exit_km_justification, "")

    def test_mechanic_cannot_deliver_a_vehicle(self):
        with self.assertRaises(PermissionDenied):
            deliver_vehicle(self.order, user=self.mechanic, exit_km=86300)

    def test_an_order_cannot_be_delivered_twice(self):
        deliver_vehicle(self.order, user=self.reception, exit_km=86300)
        with self.assertRaises(ValidationError):
            deliver_vehicle(self.order, user=self.reception, exit_km=86400)

    def test_delivery_writes_status_history_and_audit(self):
        deliver_vehicle(self.order, user=self.reception, exit_km=86300)
        self.assertTrue(
            self.order.status_history.filter(new_status=Status.DELIVERED).exists()
        )
        self.assertTrue(
            self.order.activities.filter(event_type=EventType.VEHICLE_DELIVERED).exists()
        )


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RetrievedByTests(OperationsMixin, TestCase):
    """Quem retirou, documento e assinatura: registrados, mas nunca exigidos."""

    def setUp(self):
        self.build_environment()
        self.order = self.make_order()

    @staticmethod
    def signature_data_url():
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGBA", (240, 90), (0, 0, 0, 0)).save(buffer, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()

    def test_delivery_works_without_any_of_the_optional_fields(self):
        deliver_vehicle(self.order, user=self.reception, exit_km=86300)
        self.order.refresh_from_db()

        self.assertEqual(self.order.status, Status.DELIVERED)
        self.assertEqual(self.order.received_by_name, "")
        self.assertEqual(self.order.received_by_document, "")
        self.assertFalse(self.order.delivery_signature)

    def test_records_who_took_the_car_when_it_is_not_the_owner(self):
        deliver_vehicle(
            self.order,
            user=self.reception,
            exit_km=86300,
            received_by_name="  Pedro   Alves ",
            received_by_document=" 123.456.789-00 ",
        )
        self.order.refresh_from_db()

        self.assertEqual(self.order.received_by_name, "Pedro Alves")
        self.assertEqual(self.order.received_by_document, "123.456.789-00")

    def test_audit_log_names_who_took_the_car(self):
        deliver_vehicle(
            self.order, user=self.reception, exit_km=86300, received_by_name="Pedro Alves"
        )
        activity = self.order.activities.get(event_type=EventType.VEHICLE_DELIVERED)

        self.assertIn("Pedro Alves", activity.description)
        self.assertEqual(activity.metadata.get("received_by_name"), "Pedro Alves")

    def test_audit_log_falls_back_to_the_client_name(self):
        deliver_vehicle(self.order, user=self.reception, exit_km=86300)
        activity = self.order.activities.get(event_type=EventType.VEHICLE_DELIVERED)
        self.assertIn(self.order.client.name, activity.description)

    def test_signature_drawn_on_screen_is_stored_as_an_image(self):
        self.client.force_login(self.reception)
        response = self.client.post(
            reverse("workorders:delivery", args=[self.order.uuid]),
            {
                "delivered_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
                "exit_km": 86300,
                "exit_notes": "",
                "exit_km_justification": "",
                "received_by_name": "Pedro Alves",
                "received_by_document": "",
                "signature": self.signature_data_url(),
            },
        )
        self.assertEqual(response.status_code, 302)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Status.DELIVERED)
        self.assertEqual(self.order.received_by_name, "Pedro Alves")
        self.assertTrue(self.order.delivery_signature)
        self.assertTrue(self.order.delivery_signature.name.endswith(".png"))
        self.order.delivery_signature.delete(save=False)

    def test_empty_signature_field_does_not_create_a_file(self):
        self.client.force_login(self.reception)
        self.client.post(
            reverse("workorders:delivery", args=[self.order.uuid]),
            {
                "delivered_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
                "exit_km": 86300,
                "exit_notes": "",
                "exit_km_justification": "",
                "received_by_name": "",
                "received_by_document": "",
                "signature": "",
            },
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Status.DELIVERED)
        self.assertFalse(self.order.delivery_signature)

    def test_signature_that_is_not_an_image_is_rejected(self):
        payload = base64.b64encode(b"nao sou uma imagem").decode()
        form = DeliveryForm(
            {
                "delivered_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
                "exit_km": 86300,
                "signature": "data:image/png;base64," + payload,
            },
            entry_km=self.order.entry_km,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("signature", form.errors)

    def test_signature_in_an_unexpected_format_is_rejected(self):
        form = DeliveryForm(
            {
                "delivered_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
                "exit_km": 86300,
                "signature": "javascript:alert(1)",
            },
            entry_km=self.order.entry_km,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("signature", form.errors)

    def test_rejected_signature_shows_a_message_instead_of_failing_silently(self):
        self.client.force_login(self.reception)
        response = self.client.post(
            reverse("workorders:delivery", args=[self.order.uuid]),
            {
                "delivered_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
                "exit_km": 86300,
                "exit_notes": "",
                "exit_km_justification": "",
                "received_by_name": "",
                "received_by_document": "",
                "signature": "data:image/png;base64," + base64.b64encode(b"lixo").decode(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "não é uma imagem válida")

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Status.WAITING_EVALUATION)

    def test_delivery_page_makes_clear_the_fields_are_optional(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("workorders:delivery", args=[self.order.uuid]))

        self.assertContains(response, "Quem retirou o veículo")
        self.assertContains(response, "Tudo opcional")
        self.assertContains(response, "data-signature-pad")


class CancellationTests(OperationsMixin, TestCase):
    def setUp(self):
        self.build_environment()
        self.order = self.make_order()

    def test_cancelling_records_reason_author_and_moment(self):
        cancel_service_order(self.order, user=self.reception, reason="Cliente desistiu.")
        self.order.refresh_from_db()

        self.assertEqual(self.order.status, Status.CANCELLED)
        self.assertEqual(self.order.cancellation_reason, "Cliente desistiu.")
        self.assertEqual(self.order.cancelled_by, self.reception)
        self.assertIsNotNone(self.order.cancelled_at)

    def test_reason_is_required(self):
        with self.assertRaises(ValidationError):
            cancel_service_order(self.order, user=self.reception, reason="  ")

    def test_mechanic_cannot_cancel_an_order(self):
        with self.assertRaises(PermissionDenied):
            cancel_service_order(self.order, user=self.mechanic, reason="Desistiu.")

    def test_cancelled_order_leaves_the_board_and_refuses_status_changes(self):
        from .models import ServiceOrder

        cancel_service_order(self.order, user=self.reception, reason="Cliente desistiu.")
        self.assertFalse(ServiceOrder.objects.on_board().filter(pk=self.order.pk).exists())

        with self.assertRaises(ValidationError):
            transition_service_order_status(
                self.order, new_status=Status.IN_SERVICE, user=self.reception
            )


# ---------------------------------------------------------------------------
# Auditoria
# ---------------------------------------------------------------------------


class ActivityLogTests(OperationsMixin, TestCase):
    def setUp(self):
        self.build_environment()

    def test_creating_an_order_opens_the_timeline(self):
        order = self.make_order()
        entry = order.activities.get(event_type=EventType.ORDER_CREATED)
        self.assertEqual(entry.actor, self.reception)
        self.assertIn("ABC1D23", entry.description)

    def test_every_status_change_is_recorded_with_its_author(self):
        order = self.make_order()
        transition_service_order_status(
            order, new_status=Status.IN_EVALUATION, user=self.mechanic
        )
        entry = order.activities.get(event_type=EventType.STATUS_CHANGED)
        self.assertEqual(entry.actor, self.mechanic)
        self.assertEqual(entry.metadata["new_status"], Status.IN_EVALUATION)

    def test_a_status_change_that_does_nothing_is_not_logged(self):
        order = self.make_order()
        transition_service_order_status(
            order, new_status=Status.WAITING_EVALUATION, user=self.reception
        )
        self.assertFalse(order.activities.filter(event_type=EventType.STATUS_CHANGED).exists())

    def test_diagnosis_is_only_logged_when_the_text_changes(self):
        from .services import update_diagnosis

        order = self.make_order()
        update_diagnosis(order, diagnosis="Bieleta com folga.", user=self.mechanic)
        update_diagnosis(order, diagnosis="Bieleta com folga.", user=self.mechanic)

        self.assertEqual(
            order.activities.filter(event_type=EventType.DIAGNOSIS_UPDATED).count(), 1
        )

    def test_the_log_never_stores_anything_beyond_identifiers(self):
        order = self.make_order()
        for entry in ActivityLog.objects.filter(service_order=order):
            self.assertNotIn("password", str(entry.metadata).lower())


# ---------------------------------------------------------------------------
# Views e permissões
# ---------------------------------------------------------------------------


class OperationViewTests(OperationsMixin, TestCase):
    def setUp(self):
        self.build_environment()
        self.order = self.make_order()

    def test_delivery_page_requires_permission(self):
        self.client.force_login(self.mechanic)
        response = self.client.get(reverse("workorders:delivery", args=[self.order.uuid]))
        self.assertEqual(response.status_code, 403)

    def test_reception_can_open_the_delivery_page(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("workorders:delivery", args=[self.order.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registrar saída")

    def test_delivery_form_blocks_lower_km_without_justification(self):
        self.client.force_login(self.reception)
        response = self.client.post(
            reverse("workorders:delivery", args=[self.order.uuid]),
            {
                "delivered_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
                "exit_km": 10,
                "exit_notes": "",
                "exit_km_justification": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "inferior ao de entrada")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Status.WAITING_EVALUATION)

    def test_mechanic_can_add_and_complete_a_task(self):
        self.client.force_login(self.mechanic)
        self.client.post(
            reverse("workorders:add_task", args=[self.order.uuid]), {"title": "Trocar óleo"}
        )
        task = self.order.tasks.get()

        self.client.post(
            reverse("workorders:task_action", args=[self.order.uuid, task.id, "concluir"])
        )
        task.refresh_from_db()
        self.assertEqual(task.status, TaskStatus.DONE)

    def test_unknown_task_action_is_rejected(self):
        self.client.force_login(self.reception)
        task = add_service_task(self.order, title="Trocar óleo", user=self.reception)
        response = self.client.post(
            reverse("workorders:task_action", args=[self.order.uuid, task.id, "explodir"])
        )
        self.assertEqual(response.status_code, 400)

    def test_inspection_page_lists_the_default_checklist(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("workorders:inspection", args=[self.order.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estado geral da lataria")
        self.assertContains(response, "Não verificado")

    def test_anonymous_user_is_sent_to_login(self):
        for name, args in [
            ("workorders:add_task", [self.order.uuid]),
            ("workorders:upload_photos", [self.order.uuid]),
            ("workorders:inspection", [self.order.uuid]),
            ("workorders:delivery", [self.order.uuid]),
            ("workorders:cancel", [self.order.uuid]),
        ]:
            with self.subTest(view=name):
                response = self.client.post(reverse(name, args=args))
                self.assertEqual(response.status_code, 302)
                self.assertIn("/conta/entrar/", response["Location"])


class GlobalSearchTests(OperationsMixin, TestCase):
    def setUp(self):
        self.build_environment()
        self.order = self.make_order()
        self.client.force_login(self.reception)

    def test_an_exact_plate_goes_straight_to_the_vehicle(self):
        response = self.client.get(reverse("workorders:search"), {"q": "abc1d23"})
        self.assertRedirects(response, self.vehicle.get_absolute_url())

    def test_a_plate_with_a_hyphen_is_normalised_before_searching(self):
        response = self.client.get(reverse("workorders:search"), {"q": "abc-1d23"})
        self.assertRedirects(response, self.vehicle.get_absolute_url())

    def test_results_are_grouped_by_kind(self):
        response = self.client.get(reverse("workorders:search"), {"q": "Marcos"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clientes")
        self.assertContains(response, "Marcos Ferreira")

    def test_the_order_number_finds_the_order(self):
        response = self.client.get(reverse("workorders:search"), {"q": str(self.order.number)})
        self.assertContains(response, self.order.number_display)

    def test_a_term_with_no_match_offers_a_new_entry(self):
        response = self.client.get(reverse("workorders:search"), {"q": "zzzzzz"})
        self.assertContains(response, "Nada encontrado")


class VehicleHistoryTests(OperationsMixin, TestCase):
    def setUp(self):
        self.build_environment()
        self.client.force_login(self.reception)

    def test_history_shows_services_and_the_exit_km(self):
        order = self.make_order()
        task = add_service_task(order, title="Trocar bieleta", user=self.reception)
        complete_service_task(task, user=self.mechanic)
        deliver_vehicle(order, user=self.reception, exit_km=86400)

        response = self.client.get(self.vehicle.get_absolute_url())
        self.assertContains(response, "Trocar bieleta")
        # Números saem formatados em pt-BR.
        self.assertContains(response, "86.400")

    def test_visit_count_grows_with_each_entry(self):
        first = self.make_order()
        deliver_vehicle(first, user=self.reception, exit_km=86250)
        second = self.make_order()
        deliver_vehicle(second, user=self.reception, exit_km=86300)

        response = self.client.get(self.vehicle.get_absolute_url())
        self.assertEqual(response.context["visit_count"], 2)
