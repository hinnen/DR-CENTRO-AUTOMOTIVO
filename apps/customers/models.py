from django.db import models
from django.urls import reverse

from apps.core.models import BaseModel
from apps.core.utils import format_cpf_cnpj, format_phone, normalize_phone, whatsapp_url


class ClientQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def search(self, term: str):
        term = (term or "").strip()
        if not term:
            return self

        digits = normalize_phone(term)
        condition = models.Q(name__icontains=term)
        if digits:
            condition |= models.Q(phone__contains=digits)
            condition |= models.Q(phone_whatsapp__contains=digits)
            condition |= models.Q(cpf_cnpj__contains=digits)
        return self.filter(condition)


class Client(BaseModel):
    name = models.CharField("nome", max_length=150, db_index=True)
    # As colunas são maiores que o valor normalizado de propósito: o campo do
    # formulário aceita o telefone digitado com máscara e só depois normaliza.
    phone = models.CharField("telefone", max_length=20, db_index=True)
    phone_whatsapp = models.CharField("WhatsApp", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    cpf_cnpj = models.CharField("CPF/CNPJ", max_length=20, blank=True)
    notes = models.TextField("observações", blank=True)
    is_active = models.BooleanField("ativo", default=True, db_index=True)

    objects = ClientQuerySet.as_manager()

    class Meta:
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        ordering = ["name"]
        indexes = [models.Index(fields=["name"]), models.Index(fields=["phone"])]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.name = " ".join(self.name.split())
        self.phone = normalize_phone(self.phone)
        self.phone_whatsapp = normalize_phone(self.phone_whatsapp)
        self.cpf_cnpj = "".join(c for c in self.cpf_cnpj if c.isdigit())
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("customers:detail", kwargs={"uuid": self.uuid})

    @property
    def phone_display(self) -> str:
        return format_phone(self.phone)

    @property
    def whatsapp_display(self) -> str:
        return format_phone(self.phone_whatsapp or self.phone)

    @property
    def whatsapp_url(self) -> str:
        """Abre a conversa no WhatsApp (número do Zap, senão o telefone)."""
        return whatsapp_url(self.phone_whatsapp or self.phone)

    @property
    def cpf_cnpj_display(self) -> str:
        return format_cpf_cnpj(self.cpf_cnpj)

    @property
    def first_name(self) -> str:
        return self.name.split(" ")[0] if self.name else ""
