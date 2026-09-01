"""Testes do reporte de bugs."""

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import Role
from apps.core.models import BugReport

User = get_user_model()


class BugReportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin_bug",
            password="1234",
            role=Role.ADMIN,
            first_name="Admin",
        )
        self.reception = User.objects.create_user(
            username="recep_bug",
            password="1234",
            role=Role.RECEPTION,
            first_name="Recep",
        )
        self.mechanic = User.objects.create_user(
            username="mec_bug",
            password="1234",
            role=Role.MECHANIC,
        )

    def test_authenticated_user_can_submit_bug_report(self):
        self.client.force_login(self.reception)
        payload = {
            "o_que_aconteceu": "Tela travou ao salvar",
            "o_que_esperava": "Devia ir para vistoria",
            "usuario_nome": "Recep Teste",
            "dispositivo_nome": "PC teste",
            "app_context": "desktop",
            "url_pagina": "http://testserver/",
        }
        response = self.client.post(
            reverse("api_bug_report_criar"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        report = BugReport.objects.get(pk=data["id"])
        self.assertEqual(report.usuario, self.reception)
        self.assertEqual(report.status, BugReport.STATUS_NOVO)

    def test_anonymous_cannot_submit(self):
        response = self.client.post(
            reverse("api_bug_report_criar"),
            data=json.dumps({"o_que_aconteceu": "Falhou"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)

    def test_admin_sees_list_and_detail(self):
        report = BugReport.objects.create(
            o_que_aconteceu="Erro no kanban",
            usuario_nome="Teste",
            app_context=BugReport.APP_DESKTOP,
        )
        self.client.force_login(self.admin)
        lista = self.client.get(reverse("core:bug_reports_lista"))
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, "#" + str(report.pk))
        detalhe = self.client.get(reverse("core:bug_report_detalhe", kwargs={"pk": report.pk}))
        self.assertEqual(detalhe.status_code, 200)
        self.assertContains(detalhe, "Copiar prompt Cursor")

    def test_mechanic_cannot_open_list(self):
        self.client.force_login(self.mechanic)
        response = self.client.get(reverse("core:bug_reports_lista"))
        self.assertEqual(response.status_code, 403)

    def test_desktop_base_includes_bug_script_when_logged_in(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, "bug_report.js")
        self.assertContains(response, 'name="dr-user-display"')

    def test_mobile_base_includes_bug_script(self):
        self.client.force_login(self.reception)
        response = self.client.get(reverse("mobile:home"))
        self.assertContains(response, "bug_report.js")

    def test_admin_can_change_status(self):
        report = BugReport.objects.create(o_que_aconteceu="Bug status", usuario_nome="X")
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("api_bug_report_status", kwargs={"pk": report.pk}),
            data=json.dumps({"status": "feito"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        report.refresh_from_db()
        self.assertEqual(report.status, BugReport.STATUS_FEITO)
