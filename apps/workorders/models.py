from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import BaseModel, TimeStampedModel
from apps.core.utils import humanize_duration


class Status(models.TextChoices):
    WAITING_EVALUATION = "AGUARDANDO_AVALIACAO", "Aguardando avaliação"
    IN_EVALUATION = "EM_AVALIACAO", "Em avaliação"
    WAITING_APPROVAL = "AGUARDANDO_APROVACAO", "Aguardando aprovação"
    WAITING_PART = "AGUARDANDO_PECA", "Aguardando peça"
    IN_SERVICE = "EM_MANUTENCAO", "Em manutenção"
    FINISHED = "FINALIZADO", "Finalizado"
    DELIVERED = "ENTREGUE", "Entregue"
    CANCELLED = "CANCELADO", "Cancelado"


# Status que aparecem no Kanban principal. Entregue e cancelado saem do quadro
# e passam a ser consultados pelo histórico.
BOARD_STATUSES = [
    Status.WAITING_EVALUATION,
    Status.IN_EVALUATION,
    Status.WAITING_APPROVAL,
    Status.WAITING_PART,
    Status.IN_SERVICE,
    Status.FINISHED,
]

# Status em que o veículo ainda está fisicamente na oficina.
OPEN_STATUSES = BOARD_STATUSES

CLOSED_STATUSES = [Status.DELIVERED, Status.CANCELLED]

# Classe CSS de cada status, para não espalhar cor pelos templates.
STATUS_SLUGS = {
    Status.WAITING_EVALUATION: "aguardando-avaliacao",
    Status.IN_EVALUATION: "em-avaliacao",
    Status.WAITING_APPROVAL: "aguardando-aprovacao",
    Status.WAITING_PART: "aguardando-peca",
    Status.IN_SERVICE: "em-manutencao",
    Status.FINISHED: "finalizado",
    Status.DELIVERED: "entregue",
    Status.CANCELLED: "cancelado",
}


class Priority(models.TextChoices):
    NORMAL = "NORMAL", "Normal"
    HIGH = "ALTA", "Alta"
    URGENT = "URGENTE", "Urgente"


class OrderNumberCounter(models.Model):
    """Contador da numeração de OS.

    Uma única linha, travada com ``select_for_update`` na geração do número.
    Isso evita que dois atendimentos simultâneos recebam a mesma OS.
    """

    current = models.PositiveIntegerField("último número usado", default=0)

    class Meta:
        verbose_name = "contador de OS"
        verbose_name_plural = "contador de OS"

    def __str__(self) -> str:
        return f"Última OS: {self.current}"


def signature_upload_to(instance, filename: str) -> str:
    """Assinatura da entrega, guardada junto das fotos daquela OS."""
    return f"os/{instance.pk or 'tmp'}/assinatura-{uuid4().hex}.png"


class ServiceOrderQuerySet(models.QuerySet):
    def with_related(self):
        return self.select_related("client", "vehicle", "mechanic", "location")

    def with_card_data(self):
        """Tudo o que o card do Kanban mostra, sem uma query por card.

        Sem isto, o progresso de serviços e a contagem de fotos disparariam
        duas consultas para cada veículo em tela — em um dia cheio, centenas.
        """
        return self.prefetch_related("tasks").annotate(
            photo_total=models.Count(
                "photos", filter=models.Q(photos__is_deleted=False), distinct=True
            )
        )

    def on_board(self):
        return self.filter(status__in=BOARD_STATUSES)

    def in_workshop(self):
        return self.filter(status__in=OPEN_STATUSES)

    def closed(self):
        return self.filter(status__in=CLOSED_STATUSES)

    def late(self):
        return self.filter(
            status__in=OPEN_STATUSES,
            expected_delivery_at__isnull=False,
            expected_delivery_at__lt=timezone.now(),
        )

    def search(self, term: str):
        from apps.vehicles.models import normalize_plate

        term = (term or "").strip()
        if not term:
            return self

        condition = (
            models.Q(client__name__icontains=term)
            | models.Q(vehicle__model__icontains=term)
            | models.Q(vehicle__brand__icontains=term)
        )

        plate = normalize_plate(term)
        if plate:
            condition |= models.Q(vehicle__plate__startswith=plate)

        digits = "".join(c for c in term if c.isdigit())
        if digits:
            condition |= models.Q(number=int(digits)) if digits.isdigit() else models.Q()
            condition |= models.Q(client__phone__contains=digits)

        return self.filter(condition)


class ServiceOrder(BaseModel):
    number = models.PositiveIntegerField("número da OS", unique=True, editable=False, db_index=True)

    client = models.ForeignKey(
        "customers.Client",
        verbose_name="cliente",
        related_name="service_orders",
        on_delete=models.PROTECT,
    )
    vehicle = models.ForeignKey(
        "vehicles.Vehicle",
        verbose_name="veículo",
        related_name="service_orders",
        on_delete=models.PROTECT,
    )

    entry_km = models.PositiveIntegerField("KM de entrada")
    entry_at = models.DateTimeField("data/hora de entrada", db_index=True)
    customer_complaint = models.TextField("reclamação do cliente")
    # Quem deixou o carro no pátio (pode ser diferente do titular do cadastro).
    brought_by_name = models.CharField("quem trouxe o veículo", max_length=150, blank=True)

    diagnosis = models.TextField("diagnóstico", blank=True)
    diagnosis_updated_at = models.DateTimeField("diagnóstico atualizado em", null=True, blank=True)
    diagnosis_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="diagnóstico atualizado por",
        related_name="diagnosed_orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    internal_notes = models.TextField("observações internas", blank=True)

    mechanic = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="mecânico responsável",
        related_name="assigned_orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
    )
    expected_delivery_at = models.DateTimeField("previsão de entrega", null=True, blank=True, db_index=True)

    status = models.CharField(
        "status",
        max_length=25,
        choices=Status.choices,
        default=Status.WAITING_EVALUATION,
        db_index=True,
    )
    priority = models.CharField("prioridade", max_length=10, choices=Priority.choices, default=Priority.NORMAL)

    location = models.ForeignKey(
        "vehicles.VehicleLocation",
        verbose_name="localização",
        related_name="service_orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    finished_at = models.DateTimeField("finalizado em", null=True, blank=True)

    delivered_at = models.DateTimeField("entregue em", null=True, blank=True)
    exit_km = models.PositiveIntegerField("KM de saída", null=True, blank=True)
    exit_notes = models.TextField("observação de saída", blank=True)
    exit_km_justification = models.TextField("justificativa do KM de saída", blank=True)

    # Quem apareceu para buscar o carro. Fica separado do cliente porque com
    # frequência é o filho, o motorista ou o funcionário da empresa — e é
    # justamente nesse caso que interessa ter registro de quem levou.
    received_by_name = models.CharField("retirado por", max_length=150, blank=True)
    received_by_document = models.CharField("documento de quem retirou", max_length=30, blank=True)
    delivery_signature = models.ImageField(
        "assinatura da entrega", upload_to=signature_upload_to, blank=True, null=True
    )
    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="entregue por",
        related_name="delivered_orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    cancellation_reason = models.TextField("motivo do cancelamento", blank=True)
    cancelled_at = models.DateTimeField("cancelado em", null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="cancelado por",
        related_name="cancelled_orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="registrado por",
        related_name="created_orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_demo = models.BooleanField("dado de demonstração", default=False, db_index=True)

    objects = ServiceOrderQuerySet.as_manager()

    class Meta:
        verbose_name = "ordem de serviço"
        verbose_name_plural = "ordens de serviço"
        ordering = ["-entry_at", "-number"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["entry_at"]),
            models.Index(fields=["expected_delivery_at"]),
            models.Index(fields=["number"]),
        ]

    def __str__(self) -> str:
        return f"{self.number_display} — {self.vehicle.plate}"

    def get_absolute_url(self) -> str:
        return reverse("workorders:detail", kwargs={"uuid": self.uuid})

    @property
    def number_display(self) -> str:
        return f"OS {self.number:06d}"

    @property
    def status_slug(self) -> str:
        return STATUS_SLUGS.get(self.status, "aguardando-avaliacao")

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def is_late(self) -> bool:
        if not self.expected_delivery_at or not self.is_open:
            return False
        return self.expected_delivery_at < timezone.now()

    @property
    def late_by(self) -> str:
        if not self.is_late:
            return ""
        return humanize_duration(timezone.now() - self.expected_delivery_at)

    @property
    def time_in_workshop(self) -> str:
        """Tempo total desde a entrada; congela na entrega ou no cancelamento."""
        end = self.delivered_at or self.cancelled_at or timezone.now()
        return humanize_duration(end - self.entry_at)

    @property
    def time_in_status(self) -> str:
        """Tempo no status atual, calculado a partir do histórico.

        Procura a última vez que a OS entrou no status em que está agora. Não
        há contador gravado no banco: o histórico é a fonte da verdade, o que
        evita números divergentes.
        """
        last = (
            self.status_history.filter(new_status=self.status)
            .order_by("-changed_at", "-id")
            .first()
        )
        started_at = last.changed_at if last else self.entry_at
        if self.status in CLOSED_STATUSES:
            end = self.delivered_at or self.cancelled_at or timezone.now()
        else:
            end = timezone.now()
        return humanize_duration(end - started_at)

    @property
    def km_driven(self):
        """Quanto o carro rodou entre a entrada e a saída."""
        if self.exit_km is None:
            return None
        return self.exit_km - self.entry_km

    @property
    def task_progress(self) -> dict:
        """Progresso dos serviços, ignorando os cancelados.

        Serviço cancelado não conta como pendente nem como feito: contar
        faria o card mostrar um progresso que nunca fecha.
        """
        tasks = [task for task in self.tasks.all() if task.status != TaskStatus.CANCELLED]
        total = len(tasks)
        done = sum(1 for task in tasks if task.status == TaskStatus.DONE)
        return {
            "done": done,
            "total": total,
            "percent": int(done * 100 / total) if total else 0,
            "all_done": total > 0 and done == total,
        }

    @property
    def expected_delivery_display(self) -> str:
        """Formato humano: "Hoje 17:00", "Amanhã 10:00", "02/09 14:00"."""
        if not self.expected_delivery_at:
            return "—"

        local = timezone.localtime(self.expected_delivery_at)
        today = timezone.localdate()
        delta_days = (local.date() - today).days

        if delta_days == 0:
            prefix = "Hoje"
        elif delta_days == 1:
            prefix = "Amanhã"
        elif delta_days == -1:
            prefix = "Ontem"
        else:
            prefix = local.strftime("%d/%m")

        return f"{prefix} {local.strftime('%H:%M')}"


class TaskStatus(models.TextChoices):
    PENDING = "PENDENTE", "Pendente"
    RUNNING = "EM_EXECUCAO", "Em execução"
    DONE = "CONCLUIDO", "Concluído"
    CANCELLED = "CANCELADO", "Cancelado"


class ServiceTask(TimeStampedModel):
    """Um serviço solicitado dentro da OS.

    São linhas separadas, e não um campo de texto grande, porque cada uma
    precisa ser concluída individualmente e ter responsável próprio. É o que
    permite responder "o que ainda falta neste carro" sem ler um parágrafo.
    """

    service_order = models.ForeignKey(
        ServiceOrder,
        verbose_name="ordem de serviço",
        related_name="tasks",
        on_delete=models.CASCADE,
    )
    title = models.CharField("serviço", max_length=120)
    requested_description = models.TextField("descrição solicitada", blank=True)
    performed_service = models.TextField("serviço realizado", blank=True)
    mechanic = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="mecânico",
        related_name="service_tasks",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(
        "situação", max_length=12, choices=TaskStatus.choices, default=TaskStatus.PENDING, db_index=True
    )
    position = models.PositiveSmallIntegerField("ordem", default=0)
    started_at = models.DateTimeField("iniciado em", null=True, blank=True)
    completed_at = models.DateTimeField("concluído em", null=True, blank=True)

    class Meta:
        verbose_name = "serviço da OS"
        verbose_name_plural = "serviços da OS"
        ordering = ["position", "id"]
        indexes = [models.Index(fields=["service_order", "position"])]

    def __str__(self) -> str:
        return self.title

    @property
    def is_done(self) -> bool:
        return self.status == TaskStatus.DONE

    @property
    def is_open(self) -> bool:
        return self.status in (TaskStatus.PENDING, TaskStatus.RUNNING)

    @property
    def status_slug(self) -> str:
        return self.status.lower().replace("_", "-")


class ServiceOrderStatusHistory(TimeStampedModel):
    """Registro imutável de cada mudança de status.

    Existe para responder "quem mudou, quando e de onde para onde" e para
    permitir medir gargalos depois, sem depender da memória de ninguém.
    """

    service_order = models.ForeignKey(
        ServiceOrder,
        verbose_name="ordem de serviço",
        related_name="status_history",
        on_delete=models.CASCADE,
    )
    previous_status = models.CharField("status anterior", max_length=25, choices=Status.choices, blank=True)
    new_status = models.CharField("status novo", max_length=25, choices=Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="alterado por",
        related_name="status_changes",
        on_delete=models.SET_NULL,
        null=True,
    )
    changed_at = models.DateTimeField("data/hora", default=timezone.now, db_index=True)
    note = models.TextField("observação", blank=True)

    class Meta:
        verbose_name = "histórico de status"
        verbose_name_plural = "histórico de status"
        ordering = ["-changed_at", "-id"]
        indexes = [models.Index(fields=["service_order", "-changed_at"])]

    def __str__(self) -> str:
        return f"{self.service_order.number_display}: {self.get_previous_status_display()} → {self.get_new_status_display()}"

    @property
    def new_status_slug(self) -> str:
        return STATUS_SLUGS.get(self.new_status, "")


class EventType(models.TextChoices):
    ORDER_CREATED = "OS_CRIADA", "OS criada"
    STATUS_CHANGED = "STATUS_ALTERADO", "Status alterado"
    MECHANIC_CHANGED = "MECANICO_ALTERADO", "Mecânico alterado"
    DELIVERY_CHANGED = "PREVISAO_ALTERADA", "Previsão alterada"
    LOCATION_CHANGED = "LOCALIZACAO_ALTERADA", "Localização alterada"
    DIAGNOSIS_UPDATED = "DIAGNOSTICO_ATUALIZADO", "Diagnóstico atualizado"
    TASK_ADDED = "SERVICO_ADICIONADO", "Serviço adicionado"
    TASK_STARTED = "SERVICO_INICIADO", "Serviço iniciado"
    TASK_COMPLETED = "SERVICO_CONCLUIDO", "Serviço concluído"
    TASK_REOPENED = "SERVICO_REABERTO", "Serviço reaberto"
    TASK_CANCELLED = "SERVICO_CANCELADO", "Serviço cancelado"
    PHOTOS_ADDED = "FOTOS_ADICIONADAS", "Fotos adicionadas"
    PHOTO_REMOVED = "FOTO_REMOVIDA", "Foto removida"
    INSPECTION_SAVED = "VISTORIA_SALVA", "Vistoria registrada"
    ORDER_FINISHED = "OS_FINALIZADA", "Serviço finalizado"
    VEHICLE_DELIVERED = "VEICULO_ENTREGUE", "Veículo entregue"
    ORDER_CANCELLED = "OS_CANCELADA", "OS cancelada"


# Ícone de cada evento na linha do tempo. Fica aqui e não no template para
# que a timeline não precise de uma cadeia de {% if %}.
EVENT_ICONS = {
    EventType.ORDER_CREATED: "🚗",
    EventType.STATUS_CHANGED: "↔",
    EventType.MECHANIC_CHANGED: "🔧",
    EventType.DELIVERY_CHANGED: "📅",
    EventType.LOCATION_CHANGED: "📍",
    EventType.DIAGNOSIS_UPDATED: "🩺",
    EventType.TASK_ADDED: "＋",
    EventType.TASK_STARTED: "▶",
    EventType.TASK_COMPLETED: "✓",
    EventType.TASK_REOPENED: "↺",
    EventType.TASK_CANCELLED: "✕",
    EventType.PHOTOS_ADDED: "📷",
    EventType.PHOTO_REMOVED: "🗑",
    EventType.INSPECTION_SAVED: "📋",
    EventType.ORDER_FINISHED: "🏁",
    EventType.VEHICLE_DELIVERED: "🔑",
    EventType.ORDER_CANCELLED: "⛔",
}


class ActivityLog(models.Model):
    """Trilha de auditoria da OS.

    O histórico de status responde só por status. Este log responde por tudo
    o mais: fotos, serviços, diagnóstico, entrega. É a fonte da linha do
    tempo e o que garante que nenhuma alteração relevante fique sem dono.
    """

    service_order = models.ForeignKey(
        ServiceOrder,
        verbose_name="ordem de serviço",
        related_name="activities",
        on_delete=models.CASCADE,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        related_name="activities",
        on_delete=models.SET_NULL,
        null=True,
    )
    event_type = models.CharField("evento", max_length=30, choices=EventType.choices, db_index=True)
    description = models.CharField("descrição", max_length=255)
    metadata = models.JSONField("dados", default=dict, blank=True)
    created_at = models.DateTimeField("data/hora", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "registro de atividade"
        verbose_name_plural = "registros de atividade"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["service_order", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.get_event_type_display()} — {self.description}"

    @property
    def icon(self) -> str:
        return EVENT_ICONS.get(self.event_type, "•")


# ---------------------------------------------------------------------------
# Fotos
# ---------------------------------------------------------------------------


class PhotoCategory(models.TextChoices):
    ENTRY = "ENTRADA", "Entrada"
    INSPECTION = "VISTORIA", "Vistoria"
    DIAGNOSIS = "DIAGNOSTICO", "Diagnóstico"
    SERVICE = "SERVICO", "Durante o serviço"
    EXIT = "SAIDA", "Saída"


class PhotoAngle(models.TextChoices):
    """Ângulos padrão da vistoria (estilo locadora) + extras livres."""

    FRONT = "FRENTE", "Frente"
    REAR = "TRASEIRA", "Traseira"
    LEFT = "LATERAL_ESQ", "Lateral esquerda"
    RIGHT = "LATERAL_DIR", "Lateral direita"
    DIAGONAL = "DIAGONAL", "Diagonal dianteira"
    EXTRA = "EXTRA", "Foto extra"


# Posições obrigatórias pedidas no app de vistoria (e depois no desktop).
GUIDED_PHOTO_ANGLES = [
    PhotoAngle.FRONT,
    PhotoAngle.REAR,
    PhotoAngle.LEFT,
    PhotoAngle.RIGHT,
    PhotoAngle.DIAGONAL,
]


def photo_upload_to(instance, filename: str) -> str:
    """Caminho da foto no storage.

    O nome original é descartado em favor de um UUID: nomes vindos do celular
    colidem com frequência e um upload jamais pode sobrescrever outro em
    silêncio. A pasta por OS mantém o storage navegável.
    """
    suffix = Path(filename).suffix.lower() or ".jpg"
    return f"os/{instance.service_order_id or 'tmp'}/{uuid4().hex}{suffix}"


class ServiceOrderPhotoQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(is_deleted=False)


class ServiceOrderPhoto(BaseModel):
    """Foto anexada a uma OS.

    Usa ImageField com o storage padrão do Django, sem tocar em caminho de
    disco em lugar nenhum, para que trocar por S3/R2 em produção seja
    questão de configuração.
    """

    service_order = models.ForeignKey(
        ServiceOrder,
        verbose_name="ordem de serviço",
        related_name="photos",
        on_delete=models.CASCADE,
    )
    vehicle = models.ForeignKey(
        "vehicles.Vehicle",
        verbose_name="veículo",
        related_name="photos",
        on_delete=models.CASCADE,
    )
    category = models.CharField(
        "categoria", max_length=12, choices=PhotoCategory.choices, default=PhotoCategory.ENTRY, db_index=True
    )
    angle = models.CharField(
        "ângulo / posição",
        max_length=16,
        choices=PhotoAngle.choices,
        default=PhotoAngle.EXTRA,
        blank=True,
        db_index=True,
        help_text="Posição guiada da vistoria (frente, traseira…) ou EXTRA.",
    )
    image = models.ImageField("imagem", upload_to=photo_upload_to)
    caption = models.CharField("legenda", max_length=160, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="enviada por",
        related_name="photos",
        on_delete=models.SET_NULL,
        null=True,
    )

    # Exclusão lógica: a imagem some da interface mas o registro de quem
    # apagou permanece. Foto de entrada é prova em caso de discussão.
    is_deleted = models.BooleanField("removida", default=False, db_index=True)
    deleted_at = models.DateTimeField("removida em", null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="removida por",
        related_name="deleted_photos",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    objects = ServiceOrderPhotoQuerySet.as_manager()

    class Meta:
        verbose_name = "foto"
        verbose_name_plural = "fotos"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["service_order", "category"]),
            models.Index(fields=["vehicle", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_category_display()} — OS {self.service_order.number_display}"


# ---------------------------------------------------------------------------
# Vistoria de entrada
# ---------------------------------------------------------------------------


class ItemCondition(models.TextChoices):
    NOT_CHECKED = "NAO_VERIFICADO", "Não verificado"
    OK = "OK", "OK"
    ATTENTION = "ATENCAO", "Atenção"
    DAMAGE = "AVARIA", "Avaria"


class FuelLevel(models.TextChoices):
    NOT_CHECKED = "NAO_VERIFICADO", "Não verificado"
    RESERVE = "RESERVA", "Reserva"
    QUARTER = "1_4", "1/4"
    HALF = "1_2", "1/2"
    THREE_QUARTERS = "3_4", "3/4"
    FULL = "CHEIO", "Cheio"


# Checklist padrão da vistoria de entrada.
#
# O rótulo é copiado para cada InspectionItem no momento da vistoria em vez de
# ser lido daqui na exibição. Assim, mudar esta lista amanhã não reescreve o
# que foi vistoriado ontem — e um InspectionTemplate futuro só precisa
# alimentar pares (chave, rótulo) diferentes, sem migração de dados.
DEFAULT_INSPECTION_ITEMS = [
    ("lataria", "Estado geral da lataria"),
    ("vidros", "Vidros"),
    ("farois", "Faróis"),
    ("lanternas", "Lanternas"),
    ("pneus", "Pneus"),
    ("estepe", "Estepe"),
    ("macaco", "Macaco"),
    ("chave_roda", "Chave de roda"),
    ("multimidia", "Som / multimídia"),
    ("documentos", "Documentos deixados no veículo"),
    ("objetos", "Objetos pessoais"),
    ("avarias", "Avarias aparentes"),
]


class Inspection(TimeStampedModel):
    """Vistoria de entrada do veículo.

    É opcional: o balcão precisa conseguir abrir a OS sem ela quando o cliente
    está com pressa. Mas quando existe, vale como registro do estado em que o
    carro chegou.
    """

    service_order = models.OneToOneField(
        ServiceOrder,
        verbose_name="ordem de serviço",
        related_name="inspection",
        on_delete=models.CASCADE,
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="vistoriado por",
        related_name="inspections",
        on_delete=models.SET_NULL,
        null=True,
    )
    performed_at = models.DateTimeField("vistoriado em", default=timezone.now)
    fuel_level = models.CharField(
        "nível de combustível", max_length=14, choices=FuelLevel.choices, default=FuelLevel.NOT_CHECKED
    )
    notes = models.TextField("observações gerais", blank=True)

    class Meta:
        verbose_name = "vistoria"
        verbose_name_plural = "vistorias"

    def __str__(self) -> str:
        return f"Vistoria da OS {self.service_order.number_display}"

    @property
    def summary(self) -> dict:
        items = list(self.items.all())
        return {
            "total": len(items),
            "ok": sum(1 for i in items if i.condition == ItemCondition.OK),
            "attention": sum(1 for i in items if i.condition == ItemCondition.ATTENTION),
            "damage": sum(1 for i in items if i.condition == ItemCondition.DAMAGE),
            "not_checked": sum(1 for i in items if i.condition == ItemCondition.NOT_CHECKED),
        }


class InspectionItem(models.Model):
    inspection = models.ForeignKey(
        Inspection, verbose_name="vistoria", related_name="items", on_delete=models.CASCADE
    )
    key = models.SlugField("chave", max_length=40)
    label = models.CharField("item", max_length=80)
    condition = models.CharField(
        "condição", max_length=14, choices=ItemCondition.choices, default=ItemCondition.NOT_CHECKED
    )
    note = models.CharField("observação", max_length=200, blank=True)
    position = models.PositiveSmallIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "item da vistoria"
        verbose_name_plural = "itens da vistoria"
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["inspection", "key"], name="unique_inspection_item_key"),
        ]

    def __str__(self) -> str:
        return f"{self.label}: {self.get_condition_display()}"

    @property
    def condition_slug(self) -> str:
        return self.condition.lower().replace("_", "-")
