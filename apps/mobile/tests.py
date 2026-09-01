"""Testes do PWA de vistoria em /m/."""

import io
import shutil
import tempfile
from unittest.mock import PropertyMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import Role
from apps.accounts.tests import make_user
from apps.customers.models import Client as Customer
from apps.vehicles.models import Vehicle
from apps.workorders.models import (
    DEFAULT_INSPECTION_ITEMS,
    FuelLevel,
    ItemCondition,
    PhotoCategory,
    ServiceOrderPhoto,
)
from apps.workorders.services import create_service_order, get_or_build_inspection

MEDIA_ROOT = tempfile.mkdtemp(prefix="dr-mobile-media-")


def make_image(name="foto.jpg"):
    buffer = io.BytesIO()
    Image.new("RGB", (48, 36), (21, 46, 105)).save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class MobileInspectionTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.reception = make_user("recepcao_m", Role.RECEPTION, first_name="Ana")
        self.owner = Customer.objects.create(name="Marcos Ferreira", phone="13991234567")
        self.vehicle = Vehicle.objects.create(
            client=self.owner,
            plate="ABC1D23",
            brand="Chevrolet",
            model="Onix",
            model_year=2020,
        )
        self.order = create_service_order(
            client=self.owner,
            vehicle=self.vehicle,
            entry_km=10000,
            customer_complaint="Barulho.",
            user=self.reception,
        )
        self.client.force_login(self.reception)

    def test_home_lists_open_orders(self):
        response = self.client.get(reverse("mobile:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.vehicle.plate_display)
        self.assertContains(response, self.order.number_display)

    def test_home_search_by_plate_redirects_to_inspection(self):
        response = self.client.get(reverse("mobile:home"), {"q": "abc1d23"})
        self.assertRedirects(
            response,
            reverse("mobile:inspection", kwargs={"uuid": self.order.uuid}),
        )

    def test_home_requires_login(self):
        anon = Client()
        response = anon.get(reverse("mobile:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/conta/entrar/", response["Location"])

    def test_user_without_capabilities_gets_403(self):
        with (
            patch.object(
                type(self.reception),
                "can_perform_inspection",
                new_callable=PropertyMock,
                return_value=False,
            ),
            patch.object(
                type(self.reception),
                "can_register_entry",
                new_callable=PropertyMock,
                return_value=False,
            ),
        ):
            response = self.client.get(reverse("mobile:home"))
        self.assertEqual(response.status_code, 403)

    def test_saving_inspection_persists_on_same_os(self):
        get_or_build_inspection(self.order)
        payload = {
            "fuel_level": FuelLevel.THREE_QUARTERS,
            "notes": "Entrada pelo app",
        }
        for key, _label in DEFAULT_INSPECTION_ITEMS:
            if key == "estepe":
                payload[f"condition_{key}"] = ItemCondition.DAMAGE
                payload[f"note_{key}"] = "Risco no estepe"
            elif key == "pneus":
                payload[f"condition_{key}"] = ItemCondition.ATTENTION
                payload[f"note_{key}"] = "Desgaste irregular"
            else:
                payload[f"condition_{key}"] = ItemCondition.OK
                payload[f"note_{key}"] = ""

        response = self.client.post(
            reverse("mobile:inspection", kwargs={"uuid": self.order.uuid}),
            payload,
        )
        self.assertRedirects(response, reverse("mobile:home"))

        self.order.refresh_from_db()
        inspection = self.order.inspection
        self.assertEqual(inspection.fuel_level, FuelLevel.THREE_QUARTERS)
        self.assertEqual(inspection.notes, "Entrada pelo app")
        self.assertEqual(inspection.performed_by_id, self.reception.pk)

        items = {item.key: item for item in inspection.items.all()}
        self.assertEqual(items["estepe"].condition, ItemCondition.DAMAGE)
        self.assertEqual(items["estepe"].note, "Risco no estepe")
        self.assertEqual(items["pneus"].condition, ItemCondition.ATTENTION)
        self.assertEqual(items["lataria"].condition, ItemCondition.OK)

    def test_guided_angle_photo_replaces_previous(self):
        first = self.client.post(
            reverse("mobile:upload_photos", kwargs={"uuid": self.order.uuid}),
            {
                "category": "VISTORIA",
                "angle": "FRENTE",
                "images": make_image("frente1.jpg"),
            },
        )
        self.assertEqual(first.status_code, 302)
        second = self.client.post(
            reverse("mobile:upload_photos", kwargs={"uuid": self.order.uuid}),
            {
                "category": "VISTORIA",
                "angle": "FRENTE",
                "images": make_image("frente2.jpg"),
            },
        )
        self.assertEqual(second.status_code, 302)
        from apps.workorders.models import PhotoAngle, ServiceOrderPhoto

        visible = ServiceOrderPhoto.objects.filter(
            service_order=self.order, angle=PhotoAngle.FRONT, is_deleted=False
        )
        self.assertEqual(visible.count(), 1)
        deleted = ServiceOrderPhoto.objects.filter(
            service_order=self.order, angle=PhotoAngle.FRONT, is_deleted=True
        )
        self.assertEqual(deleted.count(), 1)

    def test_inspection_page_lists_guided_slots(self):
        response = self.client.get(
            reverse("mobile:inspection", kwargs={"uuid": self.order.uuid})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Frente")
        self.assertContains(response, "Traseira")
        self.assertContains(response, "Foto extra")
        self.assertContains(response, "0/5")


    def test_manifest_and_service_worker_are_public(self):
        anon = Client()
        manifest = anon.get(reverse("mobile:manifest"))
        self.assertEqual(manifest.status_code, 200)
        self.assertIn("application/manifest+json", manifest["Content-Type"])
        self.assertEqual(manifest.json()["short_name"], "Vistoria")

        sw = anon.get(reverse("mobile:service_worker"))
        self.assertEqual(sw.status_code, 200)
        self.assertIn("javascript", sw["Content-Type"])

    def test_install_page_is_public_with_install_cta(self):
        anon = Client()
        response = anon.get(reverse("mobile:install"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DR Vistoria")
        self.assertContains(response, "data-m-install")
        self.assertContains(response, "Continuar no navegador")
        self.assertContains(response, reverse("mobile:manifest"))

    def test_home_shows_new_entry_cta_not_sistema(self):
        response = self.client.get(reverse("mobile:home"))
        self.assertContains(response, "Nova entrada")
        self.assertNotContains(response, ">Sistema<")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class MobileEntryTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.reception = make_user("recepcao_e", Role.RECEPTION, first_name="Ana")
        self.mechanic = make_user("mecanico_e", Role.MECHANIC, first_name="Carlos")
        self.owner = Customer.objects.create(name="Marcos Ferreira", phone="13991234567")
        self.vehicle = Vehicle.objects.create(
            client=self.owner,
            plate="XYZ1A23",
            brand="Fiat",
            model="Argo",
            color="Prata",
        )
        self.client.force_login(self.reception)

    def test_mechanic_cannot_open_entry(self):
        self.client.force_login(self.mechanic)
        response = self.client.get(reverse("mobile:entry_start"))
        self.assertEqual(response.status_code, 403)

    def test_existing_vehicle_opens_os_and_goes_to_inspection(self):
        response = self.client.post(
            reverse("mobile:entry_existing", kwargs={"uuid": self.vehicle.uuid}),
            {
                "name": "Marcos Ferreira",
                "phone": "13991234567",
                "entry_km": 45000,
                "customer_complaint": "Barulho na suspensão",
                "priority": "URGENTE",
                "brought_by_name": "Filho do Marcos",
            },
        )
        from apps.workorders.models import ServiceOrder

        order = ServiceOrder.objects.get(vehicle=self.vehicle)
        self.assertRedirects(
            response,
            reverse("mobile:inspection", kwargs={"uuid": order.uuid}),
        )
        self.assertEqual(order.entry_km, 45000)
        self.assertEqual(order.customer_complaint, "Barulho na suspensão")
        self.assertEqual(order.priority, "URGENTE")
        self.assertEqual(order.brought_by_name, "Filho do Marcos")

    def test_existing_entry_updates_client_name(self):
        response = self.client.post(
            reverse("mobile:entry_existing", kwargs={"uuid": self.vehicle.uuid}),
            {
                "name": "Marcos F. Atualizado",
                "phone": "13991234567",
                "entry_km": 45100,
                "customer_complaint": "Revisão",
                "priority": "NORMAL",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.name, "Marcos F. Atualizado")

    def test_existing_entry_form_shows_first_contact_sections(self):
        response = self.client.get(
            reverse("mobile:entry_existing", kwargs={"uuid": self.vehicle.uuid})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "O que o cliente reclamou")
        self.assertContains(response, "Quem trouxe o carro")
        self.assertContains(response, "Urgente")
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'data-m-wizard')
        self.assertContains(response, 'id="m-wizard-next"')
        self.assertContains(response, 'data-step="0"')
        self.assertContains(response, 'data-step="1"')
        self.assertNotContains(response, 'data-step="2"')

    def test_new_entry_form_shows_three_wizard_steps(self):
        response = self.client.get(reverse("mobile:entry_new") + "?plate=ZZZ9Z99")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Buscar cliente cadastrado")
        self.assertContains(response, 'id="m-client-uuid"')
        self.assertContains(response, 'data-step="2"')

    def test_new_entry_rejects_stale_client_uuid(self):
        response = self.client.post(
            reverse("mobile:entry_new") + "?plate=QWE2R24",
            {
                "client_uuid": "00000000-0000-0000-0000-000000000099",
                "name": "Teste",
                "phone": "13998887766",
                "plate": "QWE2R24",
                "brand": "VW",
                "model": "Gol",
                "entry_km": 1000,
                "customer_complaint": "Teste",
                "priority": "NORMAL",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Busque de novo")
        self.assertFalse(Vehicle.objects.filter(plate="QWE2R24").exists())

    def test_new_entry_links_second_vehicle_to_existing_client(self):
        response = self.client.post(
            reverse("mobile:entry_new") + "?plate=QWE1R23",
            {
                "client_uuid": str(self.owner.uuid),
                "name": "Marcos Ferreira",
                "phone": "13991234567",
                "phone_whatsapp": "",
                "plate": "QWE1R23",
                "brand": "VW",
                "model": "Polo",
                "color": "Branco",
                "model_year": 2022,
                "entry_km": 12000,
                "customer_complaint": "Segundo carro",
                "priority": "NORMAL",
                "brought_by_name": "",
            },
        )
        vehicle = Vehicle.objects.get(plate="QWE1R23")
        self.assertEqual(vehicle.client, self.owner)
        self.assertEqual(Customer.objects.filter(phone="13991234567").count(), 1)
        self.assertEqual(self.owner.vehicles.count(), 2)
        self.assertEqual(response.status_code, 302)

    def test_open_order_redirects_to_inspection_instead_of_duplicating(self):
        order = create_service_order(
            client=self.owner,
            vehicle=self.vehicle,
            entry_km=1000,
            customer_complaint="Já aberto",
            user=self.reception,
        )
        response = self.client.get(
            reverse("mobile:entry_existing", kwargs={"uuid": self.vehicle.uuid})
        )
        self.assertRedirects(
            response,
            reverse("mobile:inspection", kwargs={"uuid": order.uuid}),
        )

    def test_new_plate_creates_client_vehicle_and_order(self):
        response = self.client.post(
            reverse("mobile:entry_new") + "?plate=QWE1R23",
            {
                "name": "Paula Souza",
                "phone": "13998887766",
                "phone_whatsapp": "",
                "plate": "QWE1R23",
                "brand": "VW",
                "model": "Polo",
                "color": "Branco",
                "model_year": 2022,
                "entry_km": 12000,
                "customer_complaint": "Revisão dos 10 mil",
                "priority": "NORMAL",
                "brought_by_name": "",
            },
        )
        vehicle = Vehicle.objects.get(plate="QWE1R23")
        self.assertEqual(vehicle.client.name, "Paula Souza")
        self.assertEqual(vehicle.client.phone, "13998887766")
        order = vehicle.service_orders.get()
        self.assertRedirects(
            response,
            reverse("mobile:inspection", kwargs={"uuid": order.uuid}),
        )

    def test_plate_lookup_offers_register_when_not_found(self):
        response = self.client.get(
            reverse("mobile:entry_plate_lookup"), {"plate": "ZZZ9Z99"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cadastrar cliente e veículo")
        self.assertContains(response, "m-hit")

    def test_profile_stays_inside_mobile_app(self):
        response = self.client.get(reverse("mobile:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sair da conta")
        self.assertContains(response, "DR Vistoria")
        self.assertNotContains(response, "Dashboard")

    def test_mobile_logout_returns_to_mobile_login(self):
        response = self.client.post(reverse("mobile:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/conta/entrar/", response["Location"])
        self.assertIn("/m/", response["Location"])

    def test_entry_start_exposes_server_ocr_endpoint(self):
        response = self.client.get(reverse("mobile:entry_start"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("mobile:entry_read_plate"))
        self.assertContains(response, reverse("mobile:entry_warmup_ocr"))
        self.assertContains(response, "data-plate-ocr-url")
        self.assertContains(response, "data-plate-ocr-warmup-url")


class PlateOcrUnitTests(TestCase):
    def test_fix_old_helper_still_maps_i_to_1(self):
        from apps.mobile.plate_ocr import _fix_old

        self.assertEqual(_fix_old("JKK2I88"), "JKK2188")

    def test_pick_best_prefers_mercosul_letter_at_position_5(self):
        """5ª posição Mercosul = letra. I não vira 1 (placa antiga)."""
        from apps.mobile.plate_ocr import _pick_best

        plate, _conf = _pick_best(["[br]JKK2I88"], [0.9])
        self.assertEqual(plate, "JKK2I88")

        # OCR devolveu dígito na 5ª — corrige para letra Mercosul.
        plate2, _conf2 = _pick_best(["[br]JKK2188"], [0.9])
        self.assertEqual(plate2, "JKK2I88")

    def test_pick_mercosul_strips_region(self):
        from apps.mobile.plate_ocr import _pick_best

        plate, conf = _pick_best(["[br]REI5G32"], [0.99])
        self.assertEqual(plate, "REI5G32")
        self.assertAlmostEqual(conf, 0.99)

    def test_old_and_mercosul_same_score_tier(self):
        from apps.mobile.plate_ocr import _score

        self.assertEqual(_score("ABC1234"), _score("ABC1D23"))

    @override_settings(ENABLE_PLATE_OCR=False)
    def test_ocr_disabled_returns_clear_error(self):
        from django.core.exceptions import ValidationError

        from apps.mobile.plate_ocr import read_plate_from_upload

        with self.assertRaises(ValidationError) as ctx:
            read_plate_from_upload(make_image("placa.jpg"))
        self.assertIn("desligada", str(ctx.exception).lower())

    @patch("apps.mobile.plate_ocr._engine")
    def test_read_plate_from_upload_uses_platerec(self, mock_engine):
        from apps.mobile.plate_ocr import read_plate_from_upload

        engine = mock_engine.return_value
        engine.platedet.inference.return_value = {
            "boxes": {"boxes": [[0, 0, 10, 10]]},
            "pil": {"images": [make_image("crop.jpg")]},
        }
        engine.read.return_value = {"word": "[br]REI5G32", "confidence": 0.995}
        result = read_plate_from_upload(make_image("placa.jpg"))
        self.assertEqual(result["plate"], "REI5G32")
        self.assertGreaterEqual(result["confidence"], 0.98)
        self.assertFalse(result["needs_confirmation"])

    @patch("apps.mobile.plate_ocr._engine")
    def test_read_plate_accepts_old_format_without_pos5_ambiguity(self, mock_engine):
        from apps.mobile.plate_ocr import read_plate_from_upload

        engine = mock_engine.return_value
        engine.platedet.inference.return_value = {
            "boxes": {"boxes": [[0, 0, 10, 10]]},
            "pil": {"images": [make_image("crop.jpg")]},
        }
        # Antiga clara: 5ª = 4 (não confunde com I/L/O).
        engine.read.return_value = {"word": "[br]ABC1234", "confidence": 0.995}
        result = read_plate_from_upload(make_image("placa_antiga.jpg"))
        self.assertEqual(result["plate"], "ABC1234")

    @patch("apps.mobile.plate_ocr._engine")
    def test_low_confidence_requires_confirmation(self, mock_engine):
        from apps.mobile.plate_ocr import read_plate_from_upload

        engine = mock_engine.return_value
        engine.platedet.inference.return_value = {
            "boxes": {"boxes": [[0, 0, 10, 10]]},
            "pil": {"images": [make_image("crop.jpg")]},
        }
        engine.read.return_value = {"word": "[br]REI5G32", "confidence": 0.72}
        result = read_plate_from_upload(make_image("placa.jpg"))
        self.assertEqual(result["plate"], "REI5G32")
        self.assertTrue(result["needs_confirmation"])

    @patch("apps.mobile.plate_ocr._engine")
    def test_i_vs_1_ambiguity_requires_confirmation(self, mock_engine):
        from apps.mobile.plate_ocr import read_plate_from_upload

        engine = mock_engine.return_value
        engine.platedet.inference.return_value = {
            "boxes": {"boxes": [[0, 0, 10, 10]]},
            "pil": {"images": [make_image("crop.jpg")]},
        }
        engine.read.return_value = {"word": "[br]JKK2I88", "confidence": 0.995}
        result = read_plate_from_upload(make_image("placa.jpg"))
        self.assertEqual(result["plate"], "JKK2I88")
        self.assertTrue(result["needs_confirmation"])
        self.assertIn("JKK2188", result["alternatives"])

    def test_entry_read_plate_returns_json(self):
        reception = make_user("ocr_recep", Role.RECEPTION)
        client = Client()
        client.force_login(reception)

        with patch("apps.mobile.plate_ocr.read_plate_from_upload") as mock_read:
            mock_read.return_value = {
                "plate": "REI5G32",
                "confidence": 0.95,
                "raw": [],
                "needs_confirmation": True,
                "alternatives": [],
            }
            response = client.post(
                reverse("mobile:entry_read_plate"),
                {"image": make_image()},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["plate"], "REI5G32")
        self.assertTrue(payload["needs_confirmation"])

    def test_entry_read_plate_requires_image(self):
        reception = make_user("ocr_empty", Role.RECEPTION)
        client = Client()
        client.force_login(reception)
        response = client.post(reverse("mobile:entry_read_plate"))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    @override_settings(ENABLE_PLATE_OCR=False)
    def test_entry_warmup_ocr_reports_disabled(self):
        reception = make_user("ocr_warm_off", Role.RECEPTION)
        client = Client()
        client.force_login(reception)
        response = client.post(reverse("mobile:entry_warmup_ocr"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["warmed"])

    @patch("apps.mobile.plate_ocr.warmup_engine")
    @override_settings(ENABLE_PLATE_OCR=True)
    def test_entry_warmup_ocr_loads_engine(self, mock_warm):
        reception = make_user("ocr_warm_on", Role.RECEPTION)
        client = Client()
        client.force_login(reception)
        response = client.post(reverse("mobile:entry_warmup_ocr"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["warmed"])
        mock_warm.assert_called_once()
