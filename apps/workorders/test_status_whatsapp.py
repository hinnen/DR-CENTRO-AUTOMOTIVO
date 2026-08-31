"""Testes do aviso de status via WhatsApp (wa.me)."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role
from apps.accounts.tests import make_user
from apps.core.models import WorkshopSettings
from apps.core.services.settings import invalidate_workshop_settings_cache
from apps.core.utils import whatsapp_url
from apps.customers.models import Client
from apps.vehicles.models import Vehicle
from apps.workorders.models import ServiceOrder, Status
from apps.workorders.services import create_service_order, transition_service_order_status
from apps.workorders.status_whatsapp import status_whatsapp_notify_url


class WhatsAppUrlTests(TestCase):
    def test_whatsapp_url_with_prefilled_text(self):
        url = whatsapp_url("13997851403", text="Olá, teste")
        self.assertIn("wa.me/5513997851403", url)
        self.assertIn("text=", url)
        self.assertIn("Ol", url)


class StatusWhatsAppNotifyTests(TestCase):
    def setUp(self):
        WorkshopSettings.load()
        invalidate_workshop_settings_cache()
        self.admin = make_user("admin_wa", Role.ADMIN)
        self.client_obj = Client.objects.create(name="João Silva", phone="13999990001")
        self.vehicle = Vehicle.objects.create(
            client=self.client_obj,
            plate="ABC1D23",
            brand="VW",
            model="Gol",
        )

    def _open_order(self) -> ServiceOrder:
        return create_service_order(
            client=self.client_obj,
            vehicle=self.vehicle,
            user=self.admin,
            entry_km=1000,
            customer_complaint="Teste",
        )

    def test_disabled_by_default(self):
        order = self._open_order()
        url = status_whatsapp_notify_url(
            order,
            previous_status=Status.WAITING_EVALUATION,
            new_status=Status.IN_SERVICE,
        )
        self.assertEqual(url, "")

    def test_enabled_returns_wa_me_with_text(self):
        settings_obj = WorkshopSettings.load()
        settings_obj.auto_whatsapp_status_notify = True
        settings_obj.save()
        invalidate_workshop_settings_cache()

        order = self._open_order()
        order = transition_service_order_status(
            order, new_status=Status.IN_EVALUATION, user=self.admin
        )
        url = getattr(order, "status_whatsapp_notify_url", "")
        self.assertIn("wa.me/55", url)
        self.assertIn("text=", url)
        self.assertIn("Em%20avalia", url)

    def test_kanban_move_returns_whatsapp_url_in_json(self):
        settings_obj = WorkshopSettings.load()
        settings_obj.auto_whatsapp_status_notify = True
        settings_obj.save()
        invalidate_workshop_settings_cache()

        order = self._open_order()
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("workorders:move", kwargs={"uuid": order.uuid}),
            {"status": Status.IN_EVALUATION},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIn("wa.me", data["whatsapp_notify_url"])

    def test_skips_cancelled_status(self):
        settings_obj = WorkshopSettings.load()
        settings_obj.auto_whatsapp_status_notify = True
        settings_obj.save()
        invalidate_workshop_settings_cache()

        order = self._open_order()
        url = status_whatsapp_notify_url(
            order,
            previous_status=Status.WAITING_EVALUATION,
            new_status=Status.CANCELLED,
        )
        self.assertEqual(url, "")
