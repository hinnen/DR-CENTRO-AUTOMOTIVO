# Generated manually for BugReport

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0002_workshop_settings_whatsapp_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="BugReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("o_que_aconteceu", models.TextField(verbose_name="o que aconteceu")),
                ("o_que_esperava", models.TextField(blank=True, default="", verbose_name="o que esperava")),
                ("usuario_nome", models.CharField(blank=True, default="", max_length=120, verbose_name="nome informado")),
                (
                    "device_id",
                    models.CharField(blank=True, db_index=True, default="", max_length=64),
                ),
                ("dispositivo_nome", models.CharField(blank=True, default="", max_length=80, verbose_name="dispositivo")),
                (
                    "app_context",
                    models.CharField(
                        blank=True,
                        choices=[("desktop", "Sistema PC"), ("mobile", "App vistoria")],
                        db_index=True,
                        default="",
                        max_length=16,
                        verbose_name="contexto",
                    ),
                ),
                ("url_pagina", models.CharField(blank=True, default="", max_length=500, verbose_name="URL")),
                ("versao_app", models.CharField(blank=True, default="", max_length=32, verbose_name="versão")),
                ("user_agent", models.CharField(blank=True, default="", max_length=400)),
                ("tela", models.CharField(blank=True, default="", max_length=40, verbose_name="resolução")),
                ("print_base64", models.TextField(blank=True, default="")),
                ("print_mime", models.CharField(blank=True, default="image/jpeg", max_length=40)),
                (
                    "status",
                    models.CharField(
                        choices=[("novo", "Novo"), ("visto", "Visto"), ("feito", "Feito")],
                        db_index=True,
                        default="novo",
                        max_length=16,
                    ),
                ),
                ("notificado_email", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="criado em")),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bug_reports",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="usuário logado",
                    ),
                ),
            ],
            options={
                "verbose_name": "bug report",
                "verbose_name_plural": "bugs reportados",
                "ordering": ["-created_at"],
            },
        ),
    ]
