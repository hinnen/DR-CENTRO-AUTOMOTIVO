import re

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from apps.core.models import BaseModel, TimeStampedModel

# Placa antiga: AAA1234 | Mercosul: AAA1A23
PLATE_OLD_RE = re.compile(r"^[A-Z]{3}\d{4}$")
PLATE_MERCOSUL_RE = re.compile(r"^[A-Z]{3}\d[A-Z]\d{2}$")


def normalize_plate(value: str | None) -> str:
    """Deixa a placa em maiúsculas, sem espaços, hífens ou pontos.

    A placa é a chave de entrada do sistema inteiro: é por ela que a recepção
    encontra o veículo. Guardar sempre no mesmo formato é o que torna a busca
    confiável, não importa como foi digitada.
    """
    if not value:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def validate_plate(value: str) -> None:
    plate = normalize_plate(value)
    if not (PLATE_OLD_RE.match(plate) or PLATE_MERCOSUL_RE.match(plate)):
        raise ValidationError(
            "Placa inválida. Use o padrão antigo (ABC1234) ou Mercosul (ABC1D23).",
            code="invalid_plate",
        )


class Fuel(models.TextChoices):
    FLEX = "FLEX", "Flex"
    GASOLINE = "GASOLINA", "Gasolina"
    ETHANOL = "ETANOL", "Etanol"
    DIESEL = "DIESEL", "Diesel"
    GNV = "GNV", "GNV"
    ELECTRIC = "ELETRICO", "Elétrico"
    HYBRID = "HIBRIDO", "Híbrido"


class VehicleLocation(TimeStampedModel):
    """Onde o carro está fisicamente. Não confundir com o status da OS."""

    name = models.CharField("nome", max_length=60, unique=True)
    order = models.PositiveSmallIntegerField("ordem", default=0)
    is_active = models.BooleanField("ativa", default=True, db_index=True)
    is_demo = models.BooleanField("dado de demonstração", default=False, db_index=True)

    class Meta:
        verbose_name = "localização"
        verbose_name_plural = "localizações"
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name


class VehicleQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def search(self, term: str):
        term = (term or "").strip()
        if not term:
            return self

        plate = normalize_plate(term)
        condition = models.Q(brand__icontains=term) | models.Q(model__icontains=term)
        if plate:
            condition |= models.Q(plate__startswith=plate)
        return self.filter(condition)


class Vehicle(BaseModel):
    client = models.ForeignKey(
        "customers.Client",
        verbose_name="cliente atual",
        related_name="vehicles",
        on_delete=models.PROTECT,
    )
    # Guarda 7 caracteres, mas aceita a digitação com hífen antes de normalizar.
    plate = models.CharField("placa", max_length=10, unique=True, db_index=True)
    brand = models.CharField("marca", max_length=40)
    model = models.CharField("modelo", max_length=60)
    version = models.CharField("versão", max_length=60, blank=True)
    model_year = models.PositiveSmallIntegerField("ano do modelo", null=True, blank=True)
    manufacture_year = models.PositiveSmallIntegerField("ano de fabricação", null=True, blank=True)
    color = models.CharField("cor", max_length=30, blank=True)
    fuel = models.CharField("combustível", max_length=10, choices=Fuel.choices, blank=True)
    chassis = models.CharField("chassi", max_length=30, blank=True)
    notes = models.TextField("observações", blank=True)
    is_active = models.BooleanField("ativo", default=True, db_index=True)
    is_demo = models.BooleanField("dado de demonstração", default=False, db_index=True)

    objects = VehicleQuerySet.as_manager()

    class Meta:
        verbose_name = "veículo"
        verbose_name_plural = "veículos"
        ordering = ["plate"]
        indexes = [models.Index(fields=["plate"])]

    def __str__(self) -> str:
        return f"{self.plate} — {self.description}"

    def clean(self):
        super().clean()
        self.plate = normalize_plate(self.plate)
        validate_plate(self.plate)

    def save(self, *args, **kwargs):
        self.plate = normalize_plate(self.plate)
        validate_plate(self.plate)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("vehicles:detail", kwargs={"uuid": self.uuid})

    @property
    def description(self) -> str:
        parts = [self.brand, self.model]
        if self.model_year:
            parts.append(str(self.model_year))
        return " ".join(p for p in parts if p)

    @property
    def plate_display(self) -> str:
        """Mercosul: ABC1D23. Antiga: ABC-1234."""
        if PLATE_OLD_RE.match(self.plate):
            return f"{self.plate[:3]}-{self.plate[3:]}"
        return self.plate
