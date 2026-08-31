"""Testes da aba Configurações e preferências operacionais."""

from django.contrib.auth import authenticate
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role
from apps.accounts.services import create_mechanic_user, create_operational_user, set_user_pin
from apps.accounts.tests import make_user
from apps.core.models import WorkshopSettings
from apps.core.services.settings import invalidate_workshop_settings_cache


class WorkshopSettingsPermissionTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin_cfg", Role.ADMIN)
        self.reception = make_user("recep_cfg", Role.RECEPTION)
        self.mechanic = make_user("mec_cfg", Role.MECHANIC)
        WorkshopSettings.load()
        invalidate_workshop_settings_cache()

    def test_reception_cannot_create_mechanic_by_default(self):
        self.assertFalse(self.reception.can_create_mechanic)

    def test_reception_can_create_when_preference_enabled(self):
        settings_obj = WorkshopSettings.load()
        settings_obj.reception_can_create_mechanic = True
        settings_obj.save()
        invalidate_workshop_settings_cache()
        self.assertTrue(self.reception.can_create_mechanic)

    def test_mechanic_cannot_access_settings(self):
        self.assertFalse(self.mechanic.can_access_settings)
        response = self.client.get(reverse("core:settings_index"))
        self.assertEqual(response.status_code, 302)

    def test_reception_cannot_access_settings(self):
        self.assertFalse(self.reception.can_access_settings)
        self.client.force_login(self.reception)
        response = self.client.get(reverse("core:settings_index"))
        self.assertEqual(response.status_code, 403)

    def test_admin_sees_settings_hub(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("core:settings_index"))
        self.assertContains(response, "Usuários e PINs")
        self.assertContains(response, "Preferências")

    def test_reception_creates_mechanic_when_allowed(self):
        settings_obj = WorkshopSettings.load()
        settings_obj.reception_can_create_mechanic = True
        settings_obj.save()
        invalidate_workshop_settings_cache()

        user = create_mechanic_user(
            name="Pedro Mec",
            username="pedro_m",
            pin="1122",
            actor=self.reception,
        )
        self.assertEqual(user.username, "pedro_m")

    def test_preferences_post_updates_toggle(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("core:settings_preferences"),
            {"reception_can_create_mechanic": "on"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        invalidate_workshop_settings_cache()
        self.assertTrue(WorkshopSettings.load().reception_can_create_mechanic)


class SettingsUsersTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin_users", Role.ADMIN)
        self.reception = make_user("recep_users", Role.RECEPTION)

    def test_admin_creates_reception_user(self):
        user = create_operational_user(
            name="Ana Recepção",
            username="ana_r",
            role=Role.RECEPTION,
            pin="4455",
            actor=self.admin,
        )
        self.assertEqual(user.role, Role.RECEPTION)
        self.assertEqual(authenticate(username="ana_r", password="4455"), user)

    def test_reception_cannot_create_operational_user(self):
        from django.core.exceptions import PermissionDenied

        with self.assertRaises(PermissionDenied):
            create_operational_user(
                name="Teste",
                username="teste_x",
                role=Role.RECEPTION,
                pin="1234",
                actor=self.reception,
            )

    def test_admin_resets_pin_via_view(self):
        target = make_user("alvo_pin", Role.MECHANIC)
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("core:settings_user_pin", kwargs={"user_uuid": target.uuid}),
            {"pin": "9090"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(authenticate(username=target.username, password="9090"), target)

    def test_set_user_pin_service(self):
        target = make_user("pin_svc", Role.RECEPTION)
        set_user_pin(target=target, pin="7788", actor=self.admin)
        self.assertEqual(authenticate(username=target.username, password="7788"), target)

    def test_mechanics_url_redirects_to_users(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("core:settings_mechanics"), follow=False)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], reverse("core:settings_users"))
