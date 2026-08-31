from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.views.generic import View

from apps.accounts.models import Role
from apps.core.permissions import RoleRequiredMixin, capability_required

User = get_user_model()


class GuardedView(RoleRequiredMixin, View):
    required_capability = "can_manage_users"

    def get(self, request, *args, **kwargs):
        from django.http import HttpResponse

        return HttpResponse("ok")


@capability_required("can_deliver_vehicle")
def guarded_function_view(request):
    from django.http import HttpResponse

    return HttpResponse("ok")


class PermissionGuardTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin = User.objects.create_user(username="ana", password="x", role=Role.ADMIN)
        self.mechanic = User.objects.create_user(username="carlos", password="x", role=Role.MECHANIC)

    def test_mixin_allows_capable_user(self):
        request = self.factory.get("/")
        request.user = self.admin
        response = GuardedView.as_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_mixin_blocks_user_without_capability(self):
        request = self.factory.get("/")
        request.user = self.mechanic
        with self.assertRaises(PermissionDenied):
            GuardedView.as_view()(request)

    def test_decorator_blocks_user_without_capability(self):
        request = self.factory.get("/")
        request.user = self.mechanic
        with self.assertRaises(PermissionDenied):
            guarded_function_view(request)

    def test_decorator_allows_capable_user(self):
        request = self.factory.get("/")
        request.user = self.admin
        self.assertEqual(guarded_function_view(request).status_code, 200)


class ErrorPageTests(TestCase):
    def test_404_page_renders_custom_template(self):
        response = self.client.get("/rota-que-nao-existe/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Página não encontrada", status_code=404)


class MediaServeTests(TestCase):
    """Fotos precisam abrir mesmo com DEBUG=False (sem static() do Django)."""

    def setUp(self):
        from django.core.files.base import ContentFile

        from apps.customers.models import Client
        from apps.vehicles.models import Vehicle
        from apps.workorders.models import PhotoCategory, ServiceOrderPhoto
        from apps.workorders.services import create_service_order

        self.user = User.objects.create_user(username="recep", password="x", role=Role.RECEPTION)
        client = Client.objects.create(name="Cliente", phone="11999990000")
        vehicle = Vehicle.objects.create(
            client=client, plate="MED1A23", brand="Fiat", model="Uno", model_year=2010
        )
        order = create_service_order(
            client=client,
            vehicle=vehicle,
            entry_km=1000,
            customer_complaint="Teste foto",
            user=self.user,
        )
        # PNG mínimo 1x1
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        self.photo = ServiceOrderPhoto(
            service_order=order,
            vehicle=vehicle,
            category=PhotoCategory.INSPECTION,
            uploaded_by=self.user,
        )
        self.photo.image.save("t.png", ContentFile(png), save=True)

    def test_anonymous_cannot_fetch_media(self):
        response = self.client.get(self.photo.image.url)
        self.assertEqual(response.status_code, 404)

    def test_logged_in_user_can_fetch_media(self):
        self.client.force_login(self.user)
        response = self.client.get(self.photo.image.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(response["Content-Type"], ("image/png", "application/octet-stream"))


class TemplateHygieneTests(TestCase):
    """Guardas contra erros de template que só apareceriam na tela do usuário."""

    def _templates(self):
        from django.conf import settings

        for directory in settings.TEMPLATES[0]["DIRS"]:
            yield from Path(directory).rglob("*.html")

    def test_no_multiline_hash_comments(self):
        """``{# #}`` do Django é de uma linha só.

        Escrito em várias linhas, ele deixa de ser comentário e o texto vai
        parar na página. Comentário longo tem de usar ``{% comment %}``.
        """
        offenders = []
        for path in self._templates():
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if "{#" in line and "#}" not in line:
                    offenders.append(f"{path.name}:{number}")

        self.assertEqual(
            offenders,
            [],
            "Comentário {# #} aberto em várias linhas vaza como texto: " + ", ".join(offenders),
        )

    def test_no_unclosed_comment_blocks(self):
        for path in self._templates():
            content = path.read_text(encoding="utf-8")
            self.assertEqual(
                content.count("{% comment %}"),
                content.count("{% endcomment %}"),
                f"{path.name} tem bloco de comentário sem fechamento.",
            )
