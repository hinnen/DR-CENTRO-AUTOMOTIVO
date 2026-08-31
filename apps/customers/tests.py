from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role
from apps.accounts.tests import make_user
from apps.core.utils import format_phone, normalize_phone, whatsapp_url

from .forms import ClientForm
from .models import Client
from .services import find_by_phone


class PhoneNormalizationTests(TestCase):
    def test_removes_formatting(self):
        self.assertEqual(normalize_phone("(13) 99123-4567"), "13991234567")

    def test_drops_country_code(self):
        self.assertEqual(normalize_phone("+55 13 99123-4567"), "13991234567")

    def test_handles_landline(self):
        self.assertEqual(normalize_phone("13 3221-5588"), "1332215588")

    def test_empty_value_is_empty_string(self):
        self.assertEqual(normalize_phone(""), "")
        self.assertEqual(normalize_phone(None), "")

    def test_display_format_mobile_and_landline(self):
        self.assertEqual(format_phone("13991234567"), "(13) 99123-4567")
        self.assertEqual(format_phone("1332215588"), "(13) 3221-5588")

    def test_whatsapp_url_adds_brazil_country_code(self):
        self.assertEqual(whatsapp_url("(13) 99785-1403"), "https://wa.me/5513997851403")
        self.assertEqual(whatsapp_url(""), "")


class ClientModelTests(TestCase):
    def test_phone_is_stored_normalized(self):
        client = Client.objects.create(name="Marcos Ferreira", phone="(13) 99123-4567")
        client.refresh_from_db()
        self.assertEqual(client.phone, "13991234567")

    def test_name_whitespace_is_collapsed(self):
        client = Client.objects.create(name="  Marcos   Ferreira ", phone="13991234567")
        self.assertEqual(client.name, "Marcos Ferreira")

    def test_cpf_is_stored_without_punctuation(self):
        client = Client.objects.create(
            name="Marcos", phone="13991234567", cpf_cnpj="123.456.789-09"
        )
        self.assertEqual(client.cpf_cnpj, "12345678909")


class ClientSearchTests(TestCase):
    def setUp(self):
        Client.objects.create(name="Juliana Prado", phone="13992345678")
        Client.objects.create(name="Roberto Menezes", phone="13993456789")

    def test_search_by_partial_name(self):
        self.assertEqual(Client.objects.search("juli").count(), 1)

    def test_search_by_formatted_phone_finds_normalized_record(self):
        self.assertEqual(Client.objects.search("(13) 99234-5678").count(), 1)

    def test_find_by_phone_detects_duplicate(self):
        self.assertEqual(find_by_phone("13992345678").count(), 1)
        self.assertEqual(find_by_phone("13900000000").count(), 0)


class ClientFormTests(TestCase):
    def test_rejects_phone_without_area_code(self):
        form = ClientForm(data={"name": "Teste", "phone": "991234567"})
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)

    def test_accepts_formatted_phone(self):
        form = ClientForm(data={"name": "Teste", "phone": "(13) 99123-4567"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone"], "13991234567")

    def test_rejects_cpf_with_wrong_length(self):
        form = ClientForm(data={"name": "Teste", "phone": "13991234567", "cpf_cnpj": "123"})
        self.assertFalse(form.is_valid())
        self.assertIn("cpf_cnpj", form.errors)


class ClientViewPermissionTests(TestCase):
    def setUp(self):
        self.client_record = Client.objects.create(name="Fernanda Lopes", phone="13994567890")

    def test_list_requires_login(self):
        response = self.client.get(reverse("customers:list"))
        self.assertEqual(response.status_code, 302)

    def test_reception_can_open_create_form(self):
        self.client.force_login(make_user("recepcao1", Role.RECEPTION))
        response = self.client.get(reverse("customers:create"))
        self.assertEqual(response.status_code, 200)

    def test_mechanic_cannot_create_client(self):
        self.client.force_login(make_user("mecanico1", Role.MECHANIC))
        response = self.client.get(reverse("customers:create"))
        self.assertEqual(response.status_code, 403)

    def test_mechanic_can_read_client_detail(self):
        self.client.force_login(make_user("mecanico2", Role.MECHANIC))
        response = self.client.get(
            reverse("customers:detail", kwargs={"uuid": self.client_record.uuid})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fernanda Lopes")

    def test_phone_lookup_warns_about_existing_client(self):
        self.client.force_login(make_user("recepcao2", Role.RECEPTION))
        response = self.client.get(
            reverse("customers:phone_lookup"), {"phone": "(13) 99456-7890"}
        )
        self.assertContains(response, "Já existe um cliente com este telefone")
