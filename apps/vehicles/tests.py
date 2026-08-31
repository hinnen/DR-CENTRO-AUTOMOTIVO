from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role
from apps.accounts.tests import make_user
from apps.customers.models import Client

from .forms import VehicleForm
from .models import Vehicle, normalize_plate, validate_plate
from .services import build_plate_lookup_context, find_by_plate


class PlateNormalizationTests(TestCase):
    def test_uppercases_and_strips_separators(self):
        self.assertEqual(normalize_plate("abc-1d23"), "ABC1D23")
        self.assertEqual(normalize_plate(" abc 1234 "), "ABC1234")
        self.assertEqual(normalize_plate("abc.1234"), "ABC1234")
        self.assertEqual(normalize_plate("AFG-2562"), "AFG2562")

    def test_empty_value(self):
        self.assertEqual(normalize_plate(None), "")

    def test_format_display_old_and_mercosul(self):
        from .models import format_plate_display

        self.assertEqual(format_plate_display("afg2562"), "AFG-2562")
        self.assertEqual(format_plate_display("AFG-2562"), "AFG-2562")
        self.assertEqual(format_plate_display("abc1d23"), "ABC1D23")

    def test_accepts_old_and_mercosul_formats(self):
        validate_plate("ABC1234")
        validate_plate("abc-1d23")
        validate_plate("AFG-2562")

    def test_rejects_invalid_formats(self):
        for invalid in ["AB1234", "ABCD123", "1234ABC", "ABC12E4", ""]:
            with self.subTest(plate=invalid):
                with self.assertRaises(ValidationError):
                    validate_plate(invalid)


class VehicleModelTests(TestCase):
    def setUp(self):
        self.owner = Client.objects.create(name="Paulo Dias", phone="13995678901")

    def test_plate_is_normalized_on_save(self):
        vehicle = Vehicle.objects.create(
            client=self.owner, plate="abc-1d23", brand="Chevrolet", model="Onix"
        )
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.plate, "ABC1D23")

    def test_duplicate_plate_is_rejected_even_when_typed_differently(self):
        Vehicle.objects.create(client=self.owner, plate="ABC1D23", brand="Chevrolet", model="Onix")
        with self.assertRaises(IntegrityError):
            Vehicle.objects.create(client=self.owner, plate="abc-1d23", brand="Fiat", model="Argo")

    def test_invalid_plate_is_rejected_on_save(self):
        with self.assertRaises(ValidationError):
            Vehicle.objects.create(client=self.owner, plate="XX123", brand="Fiat", model="Argo")

    def test_display_adds_hyphen_only_for_old_format(self):
        old = Vehicle(client=self.owner, plate="ABC1234")
        mercosul = Vehicle(client=self.owner, plate="ABC1D23")
        self.assertEqual(old.plate_display, "ABC-1234")
        self.assertEqual(mercosul.plate_display, "ABC1D23")

    def test_description_joins_brand_model_and_year(self):
        vehicle = Vehicle(client=self.owner, plate="ABC1D23", brand="Fiat", model="Argo", model_year=2021)
        self.assertEqual(vehicle.description, "Fiat Argo 2021")


class VehicleFormTests(TestCase):
    def setUp(self):
        self.owner = Client.objects.create(name="Camila Rodrigues", phone="13996789012")

    def test_form_reports_duplicate_plate_instead_of_crashing(self):
        Vehicle.objects.create(client=self.owner, plate="ABC1D23", brand="Chevrolet", model="Onix")
        form = VehicleForm(data={"plate": "abc1d23", "brand": "Fiat", "model": "Argo"})
        self.assertFalse(form.is_valid())
        self.assertIn("Já existe um veículo cadastrado com esta placa.", form.errors["plate"])

    def test_editing_the_same_vehicle_keeps_its_plate_valid(self):
        vehicle = Vehicle.objects.create(
            client=self.owner, plate="ABC1D23", brand="Chevrolet", model="Onix"
        )
        form = VehicleForm(
            data={"plate": "ABC1D23", "brand": "Chevrolet", "model": "Onix"}, instance=vehicle
        )
        self.assertTrue(form.is_valid(), form.errors)


class VehicleLookupTests(TestCase):
    def setUp(self):
        self.owner = Client.objects.create(name="Anderson Silva", phone="13997890123")
        self.vehicle = Vehicle.objects.create(
            client=self.owner, plate="DEF2G45", brand="Volkswagen", model="Gol"
        )

    def test_find_by_plate_ignores_formatting(self):
        self.assertEqual(find_by_plate("def-2g45"), self.vehicle)
        self.assertEqual(find_by_plate("DEF2G45"), self.vehicle)

    def test_find_by_plate_old_format_with_or_without_hyphen(self):
        old = Vehicle.objects.create(
            client=self.owner, plate="AFG2562", brand="Fiat", model="Uno"
        )
        self.assertEqual(find_by_plate("AFG-2562"), old)
        self.assertEqual(find_by_plate("afg2562"), old)
        self.assertEqual(find_by_plate("AFG 2562"), old)

    def test_find_by_plate_matches_dirty_hyphen_in_database(self):
        dirty = Vehicle(client=self.owner, plate="SGH4563", brand="VW", model="Gol")
        dirty.save()
        # Simula registro legado gravado com traço (bypass do save).
        Vehicle.objects.filter(pk=dirty.pk).update(plate="SGH-4563")
        self.assertEqual(find_by_plate("SGH4563"), dirty)
        self.assertEqual(find_by_plate("sgh-4563"), dirty)

    def test_find_by_plate_returns_none_when_missing(self):
        self.assertIsNone(find_by_plate("ZZZ9Z99"))

    def test_plate_lookup_context_waits_for_full_plate(self):
        ctx = build_plate_lookup_context(plate="ABC", raw="ABC")
        self.assertTrue(ctx.get("typing"))
        self.assertEqual(ctx["remaining"], 4)
        self.assertNotIn("not_found", ctx)

    def test_plate_lookup_context_finds_vehicle_when_complete(self):
        ctx = build_plate_lookup_context(plate="DEF2G45", raw="DEF-2G45")
        self.assertIn("summary", ctx)
        self.assertEqual(ctx["summary"]["vehicle"].pk, self.vehicle.pk)

    def test_plate_lookup_context_not_found_offers_display(self):
        ctx = build_plate_lookup_context(plate="AFG2562", raw="AFG-2562")
        self.assertTrue(ctx.get("not_found"))
        self.assertEqual(ctx["plate_display"], "AFG-2562")


class VehicleViewTests(TestCase):
    def setUp(self):
        self.owner = Client.objects.create(name="Patrícia Gomes", phone="13998901234")
        self.vehicle = Vehicle.objects.create(
            client=self.owner, plate="GHI3J67", brand="Fiat", model="Argo"
        )

    def test_detail_requires_login(self):
        response = self.client.get(reverse("vehicles:detail", kwargs={"uuid": self.vehicle.uuid}))
        self.assertEqual(response.status_code, 302)

    def test_detail_shows_plate_and_owner(self):
        self.client.force_login(make_user("recepcao3", Role.RECEPTION))
        response = self.client.get(reverse("vehicles:detail", kwargs={"uuid": self.vehicle.uuid}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GHI3J67")
        self.assertContains(response, "Patrícia Gomes")

    def test_mechanic_cannot_edit_vehicle(self):
        self.client.force_login(make_user("mecanico3", Role.MECHANIC))
        response = self.client.get(reverse("vehicles:update", kwargs={"uuid": self.vehicle.uuid}))
        self.assertEqual(response.status_code, 403)
