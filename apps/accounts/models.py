"""Usuário customizado com os perfis operacionais da oficina."""

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import UUIDModel


class Role(models.TextChoices):
    ADMIN = "ADMINISTRADOR", "Administrador"
    RECEPTION = "RECEPCAO", "Recepção"
    MECHANIC = "MECANICO", "Mecânico"


class User(UUIDModel, AbstractUser):
    role = models.CharField(
        "perfil",
        max_length=20,
        choices=Role.choices,
        default=Role.RECEPTION,
        db_index=True,
    )
    phone = models.CharField("telefone", max_length=20, blank=True)
    is_demo = models.BooleanField(
        "dado de demonstração",
        default=False,
        db_index=True,
        help_text="Usuário criado pelo pacote de exemplos.",
    )

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ["first_name", "username"]

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.username

    @property
    def short_name(self) -> str:
        return self.first_name or self.username

    @property
    def initials(self) -> str:
        parts = [p for p in (self.first_name, self.last_name) if p]
        if not parts:
            return self.username[:2].upper()
        return "".join(p[0] for p in parts[:2]).upper()

    # As checagens abaixo são a fonte única de verdade das permissões.
    # Superusuário sempre passa; o restante depende do perfil.

    @property
    def is_admin_role(self) -> bool:
        return self.is_superuser or self.role == Role.ADMIN

    @property
    def is_reception(self) -> bool:
        return self.role == Role.RECEPTION

    @property
    def is_mechanic(self) -> bool:
        return self.role == Role.MECHANIC

    @property
    def can_manage_customers(self) -> bool:
        """Criar e editar clientes e veículos."""
        return self.is_admin_role or self.is_reception

    @property
    def can_delete_records(self) -> bool:
        """Excluir/inativar cadastros e remover fotos."""
        return self.is_admin_role

    @property
    def can_manage_users(self) -> bool:
        return self.is_admin_role

    @property
    def can_create_mechanic(self) -> bool:
        """Cadastro rápido / Configurações → Mecânicos."""
        if self.can_manage_users:
            return True
        if self.is_reception:
            from apps.core.services.settings import reception_can_create_mechanic

            return reception_can_create_mechanic()
        return False

    @property
    def can_access_settings(self) -> bool:
        """Hub Configurações — somente administradores."""
        return self.can_manage_users

    @property
    def can_register_entry(self) -> bool:
        """Abrir nova entrada e gerar OS."""
        return self.is_admin_role or self.is_reception

    @property
    def can_deliver_vehicle(self) -> bool:
        """Registrar saída/entrega do veículo."""
        return self.is_admin_role or self.is_reception

    @property
    def can_update_diagnosis(self) -> bool:
        return True

    @property
    def can_change_status(self) -> bool:
        return True

    @property
    def can_manage_tasks(self) -> bool:
        """Adicionar, concluir e cancelar serviços da OS.

        Liberado para todos os perfis: quem descobre que falta um serviço
        costuma ser o mecânico com o carro no elevador, e obrigá-lo a chamar
        a recepção só para registrar isso faria o sistema ser contornado.
        """
        return True

    @property
    def can_upload_photos(self) -> bool:
        return True

    @property
    def can_delete_photos(self) -> bool:
        """Mecânico não remove foto: ela é prova do estado do veículo."""
        return self.is_admin_role or self.is_reception

    @property
    def can_perform_inspection(self) -> bool:
        return True

    @property
    def can_cancel_order(self) -> bool:
        return self.is_admin_role or self.is_reception
