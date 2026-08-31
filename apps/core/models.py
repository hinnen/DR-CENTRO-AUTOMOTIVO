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
