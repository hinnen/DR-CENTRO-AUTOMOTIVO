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
