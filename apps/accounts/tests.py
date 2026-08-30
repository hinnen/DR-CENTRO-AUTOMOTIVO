from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Role

User = get_user_model()


def make_user(username: str, role: str, **extra) -> User:
    return User.objects.create_user(username=username, password="senha-forte-123", role=role, **extra)


class RoleCapabilityTests(TestCase):
    def test_admin_has_full_access(self):
        user = make_user("ana", Role.ADMIN)
        self.assertTrue(user.is_admin_role)
        self.assertTrue(user.can_manage_customers)
        self.assertTrue(user.can_manage_users)
        self.assertTrue(user.can_delete_records)
        self.assertTrue(user.can_register_entry)
        self.assertTrue(user.can_deliver_vehicle)

    def test_reception_operates_but_does_not_manage_users(self):
        user = make_user("maria", Role.RECEPTION)
        self.assertTrue(user.can_manage_customers)
        self.assertTrue(user.can_register_entry)
        self.assertTrue(user.can_deliver_vehicle)
        self.assertFalse(user.can_manage_users)
        self.assertFalse(user.can_delete_records)

    def test_mechanic_cannot_manage_customers_or_deliver(self):
        user = make_user("carlos", Role.MECHANIC)
        self.assertTrue(user.is_mechanic)
        self.assertTrue(user.can_update_diagnosis)
        self.assertTrue(user.can_change_status)
        self.assertFalse(user.can_manage_customers)
        self.assertFalse(user.can_manage_users)
        self.assertFalse(user.can_delete_records)
        self.assertFalse(user.can_deliver_vehicle)

    def test_superuser_is_treated_as_admin_regardless_of_role(self):
        user = User.objects.create_superuser(username="root", password="senha-forte-123")
        user.role = Role.MECHANIC
        self.assertTrue(user.is_admin_role)
        self.assertTrue(user.can_manage_users)

    def test_default_role_is_reception(self):
        user = User.objects.create_user(username="novo", password="senha-forte-123")
        self.assertEqual(user.role, Role.RECEPTION)


class UserDisplayTests(TestCase):
    def test_display_name_prefers_full_name(self):
        user = make_user("jsilva", Role.RECEPTION, first_name="João", last_name="Silva")
        self.assertEqual(user.display_name, "João Silva")
        self.assertEqual(user.initials, "JS")

    def test_display_name_falls_back_to_username(self):
        user = make_user("jsilva2", Role.RECEPTION)
        self.assertEqual(user.display_name, "jsilva2")
        self.assertEqual(user.initials, "JS")


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.user = make_user("maria", Role.RECEPTION, first_name="Maria")

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)

    def test_login_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "maria", "password": "senha-forte-123"},
        )
        self.assertRedirects(response, reverse("dashboard:home"))

    def test_authenticated_user_reaches_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Na oficina")
        self.assertContains(response, "Dashboard")

    def test_invalid_credentials_show_error(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "maria", "password": "errada"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Usuário ou senha incorretos.")

    def test_logout_requires_post_and_redirects_to_login(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))
