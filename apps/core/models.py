"""Bases reutilizadas pelos models de todo o projeto."""

import uuid

from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("criado em", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Identificador público, usado nas URLs para não expor o id sequencial."""

    uuid = models.UUIDField("identificador público", default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    class Meta:
        abstract = True


class WorkshopSettings(models.Model):
    """Preferências operacionais da oficina (registro único, pk=1)."""

    reception_can_create_mechanic = models.BooleanField(
        "recepção pode cadastrar mecânicos",
        default=False,
        help_text=(
            "Quando ativo, usuários de recepção também podem criar mecânicos "
            "pelo cadastro rápido e pela aba Configurações."
        ),
    )
    auto_whatsapp_status_notify = models.BooleanField(
        "avisar cliente no WhatsApp ao mudar status",
        default=False,
        help_text=(
            "Abre o WhatsApp com mensagem pronta quando o status da OS muda "
            "(Kanban, detalhe ou entrega). Usa wa.me — não envia sozinho."
        ),
    )
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "configuração da oficina"
        verbose_name_plural = "configurações da oficina"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        from apps.core.services.settings import invalidate_workshop_settings_cache

        invalidate_workshop_settings_cache()

    @classmethod
    def load(cls) -> "WorkshopSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self) -> str:
        return "Configurações da oficina"


class BugReport(models.Model):
    """Feedback / bug reportado pela equipe (botão flutuante global)."""

    STATUS_NOVO = "novo"
    STATUS_VISTO = "visto"
    STATUS_FEITO = "feito"
    STATUS_CHOICES = (
        (STATUS_NOVO, "Novo"),
        (STATUS_VISTO, "Visto"),
        (STATUS_FEITO, "Feito"),
    )

    APP_DESKTOP = "desktop"
    APP_MOBILE = "mobile"
    APP_CHOICES = (
        (APP_DESKTOP, "Sistema PC"),
        (APP_MOBILE, "App vistoria"),
    )

    o_que_aconteceu = models.TextField("o que aconteceu")
    o_que_esperava = models.TextField("o que esperava", blank=True, default="")
    usuario_nome = models.CharField("nome informado", max_length=120, blank=True, default="")
    usuario = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bug_reports",
        verbose_name="usuário logado",
    )
    device_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    dispositivo_nome = models.CharField("dispositivo", max_length=80, blank=True, default="")
    app_context = models.CharField(
        "contexto",
        max_length=16,
        choices=APP_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )
    url_pagina = models.CharField("URL", max_length=500, blank=True, default="")
    versao_app = models.CharField("versão", max_length=32, blank=True, default="")
    user_agent = models.CharField(max_length=400, blank=True, default="")
    tela = models.CharField("resolução", max_length=40, blank=True, default="")
    print_base64 = models.TextField(blank=True, default="")
    print_mime = models.CharField(max_length=40, blank=True, default="image/jpeg")
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_NOVO,
        db_index=True,
    )
    notificado_email = models.BooleanField(default=False)
    created_at = models.DateTimeField("criado em", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "bug report"
        verbose_name_plural = "bugs reportados"

    def __str__(self) -> str:
        trecho = (self.o_que_aconteceu or "")[:40]
        return f"#{self.pk} {self.usuario_nome or '?'} — {trecho}"
