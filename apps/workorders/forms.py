import base64
import binascii
import io
from datetime import datetime
from pathlib import Path

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.vehicles.models import VehicleLocation

from .models import (
    BOARD_STATUSES,
    FuelLevel,
    ItemCondition,
    PhotoAngle,
    PhotoCategory,
    Priority,
    ServiceOrder,
    ServiceTask,
    Status,
)


def mechanic_queryset():
    return User.objects.filter(role=Role.MECHANIC, is_active=True)


class LocalDateTimeInput(forms.DateTimeInput):
    """Campo nativo de data e hora do navegador.

    O ``datetime-local`` exige exatamente ``aaaa-mm-ddThh:mm``. O Django já
    entrega o valor convertido para o fuso local (e sem tzinfo), então aqui só
    resta formatar.
    """

    input_type = "datetime-local"

    def format_value(self, value):
        if not value:
            return ""
        if isinstance(value, datetime):
            if timezone.is_aware(value):
                value = timezone.localtime(value)
            return value.strftime("%Y-%m-%dT%H:%M")
        return value


class ServiceOrderEntryForm(forms.ModelForm):
    """Dados da etapa "Entrada" do fluxo de Nova Entrada."""

    class Meta:
        model = ServiceOrder
        fields = [
            "entry_km",
            "entry_at",
            "customer_complaint",
            "mechanic",
            "expected_delivery_at",
            "location",
            "priority",
            "internal_notes",
        ]
        widgets = {
            "entry_km": forms.NumberInput(
                attrs={"placeholder": "86210", "inputmode": "numeric", "min": 0}
            ),
            "entry_at": LocalDateTimeInput(),
            "customer_complaint": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Barulho dianteiro ao passar em buraco."}
            ),
            "expected_delivery_at": LocalDateTimeInput(),
            "internal_notes": forms.Textarea(attrs={"rows": 2, "placeholder": "opcional"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mechanic"].queryset = mechanic_queryset()
        self.fields["mechanic"].empty_label = "Definir depois"
        self.fields["mechanic"].required = False
        self.fields["location"].queryset = VehicleLocation.objects.filter(is_active=True)
        self.fields["location"].empty_label = "Definir depois"
        self.fields["location"].required = False
        self.fields["priority"].initial = Priority.NORMAL

        if not self.instance.pk and not self.initial.get("entry_at"):
            self.initial["entry_at"] = timezone.localtime()

    def clean_entry_km(self):
        km = self.cleaned_data.get("entry_km")
        if km is None or km < 0:
            raise forms.ValidationError("Informe a quilometragem do painel.")
        return km

    def clean_customer_complaint(self):
        value = (self.cleaned_data.get("customer_complaint") or "").strip()
        if not value:
            raise forms.ValidationError("Descreva o que o cliente relatou.")
        return value


class StatusChangeForm(forms.Form):
    status = forms.ChoiceField(
        label="Novo status",
        choices=[(s.value, s.label) for s in BOARD_STATUSES],
    )
    note = forms.CharField(
        label="Observação",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "opcional"}),
    )


class MechanicChangeForm(forms.Form):
    mechanic = forms.ModelChoiceField(
        label="Mecânico responsável",
        queryset=User.objects.none(),
        required=False,
        empty_label="Sem responsável",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mechanic"].queryset = mechanic_queryset()


class LocationChangeForm(forms.Form):
    location = forms.ModelChoiceField(
        label="Localização do veículo",
        queryset=VehicleLocation.objects.none(),
        required=False,
        empty_label="Sem localização",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location"].queryset = VehicleLocation.objects.filter(is_active=True)


def mechanic_select_field(*, selected=None, empty_label="Sem responsável"):
    form = MechanicChangeForm(initial={"mechanic": selected})
    form.fields["mechanic"].empty_label = empty_label
    return form["mechanic"]


def location_select_field(*, selected=None, empty_label="Sem localização"):
    form = LocationChangeForm(initial={"location": selected})
    form.fields["location"].empty_label = empty_label
    return form["location"]


class QuickMechanicForm(forms.Form):
    name = forms.CharField(
        label="Nome completo",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Carlos Silva"}),
    )
    username = forms.CharField(
        label="Usuário",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "username", "placeholder": "carlos"}),
    )
    pin = forms.CharField(
        label="PIN (4 dígitos)",
        min_length=4,
        max_length=4,
        widget=forms.PasswordInput(
            attrs={
                "inputmode": "numeric",
                "pattern": "[0-9]{4}",
                "maxlength": "4",
                "autocomplete": "new-password",
                "placeholder": "••••",
            }
        ),
        help_text="Senha de login do mecânico — exatamente 4 números.",
    )
    phone = forms.CharField(
        label="Telefone",
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "opcional"}),
    )


class QuickLocationForm(forms.Form):
    name = forms.CharField(
        label="Nome da localização",
        max_length=60,
        widget=forms.TextInput(attrs={"placeholder": "Ex.: Elevador 1, Pátio A"}),
    )


class ExpectedDeliveryForm(forms.Form):
    expected_delivery_at = forms.DateTimeField(
        label="Previsão de entrega", required=False, widget=LocalDateTimeInput()
    )


class DiagnosisForm(forms.Form):
    diagnosis = forms.CharField(
        label="Diagnóstico",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 5, "placeholder": "O que foi identificado no veículo."}
        ),
    )


# ---------------------------------------------------------------------------
# Serviços da OS
# ---------------------------------------------------------------------------


class ServiceTaskForm(forms.ModelForm):
    """Adiciona um serviço à OS. Só o título é obrigatório."""

    class Meta:
        model = ServiceTask
        fields = ["title", "requested_description", "mechanic"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Trocar óleo", "autocomplete": "off"}),
            "requested_description": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Detalhes (opcional)"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mechanic"].queryset = mechanic_queryset()
        self.fields["mechanic"].empty_label = "Sem responsável"
        self.fields["mechanic"].required = False

    def clean_title(self):
        title = " ".join((self.cleaned_data.get("title") or "").split())
        if not title:
            raise forms.ValidationError("Informe o serviço.")
        return title


class CompleteTaskForm(forms.Form):
    performed_service = forms.CharField(
        label="Serviço realizado",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "O que foi feito (opcional)"}),
    )


# ---------------------------------------------------------------------------
# Fotos
# ---------------------------------------------------------------------------

ALLOWED_PHOTO_SUFFIXES = {f".{ext}" for ext in settings.ALLOWED_IMAGE_EXTENSIONS}
ALLOWED_PHOTO_MIMES = set(settings.ALLOWED_IMAGE_MIME_TYPES)


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """``FileField`` que aceita vários arquivos.

    O ``FileField`` do Django valida um arquivo só; com ``multiple`` o widget
    devolve uma lista e a validação padrão rejeitaria tudo. Aqui a validação
    de arquivo é aplicada item a item e o resultado é sempre uma lista.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultiFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        clean_one = super().clean
        if isinstance(data, (list, tuple)):
            return [clean_one(item, initial) for item in data]
        return [clean_one(data, initial)]


class PhotoUploadForm(forms.Form):
    """Envio de uma ou várias fotos de uma vez.

    A validação é feita no servidor porque o ``accept`` do input é apenas uma
    sugestão ao navegador: qualquer cliente pode enviar outra coisa.
    """

    images = MultipleFileField(
        label="Fotos",
        widget=MultiFileInput(
            attrs={
                "multiple": True,
                "accept": ",".join(settings.ALLOWED_IMAGE_MIME_TYPES),
                # Abre a câmera direto no celular; no desktop é ignorado.
                "capture": "environment",
            }
        ),
    )
    category = forms.ChoiceField(
        label="Categoria", choices=PhotoCategory.choices, initial=PhotoCategory.ENTRY
    )
    angle = forms.ChoiceField(
        label="Ângulo",
        choices=PhotoAngle.choices,
        required=False,
        initial=PhotoAngle.EXTRA,
    )
    caption = forms.CharField(
        label="Legenda",
        required=False,
        max_length=160,
        widget=forms.TextInput(attrs={"placeholder": "opcional"}),
    )

    def clean_angle(self):
        return self.cleaned_data.get("angle") or PhotoAngle.EXTRA

    def clean_images(self):
        files = [upload for upload in self.cleaned_data.get("images") or [] if upload]
        if not files:
            raise forms.ValidationError("Selecione ao menos uma foto.")
        if len(files) > 20:
            raise forms.ValidationError("Envie no máximo 20 fotos por vez.")

        for upload in files:
            suffix = Path(upload.name).suffix.lower()
            if suffix not in ALLOWED_PHOTO_SUFFIXES:
                raise forms.ValidationError(
                    f"“{upload.name}”: use apenas JPG, PNG ou WEBP."
                )
            if upload.content_type not in ALLOWED_PHOTO_MIMES:
                raise forms.ValidationError(f"“{upload.name}” não é uma imagem válida.")
            if upload.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
                raise forms.ValidationError(
                    f"“{upload.name}” tem mais de {settings.MAX_UPLOAD_SIZE_MB} MB."
                )
            # Último filtro: o Pillow precisa reconhecer o conteúdo. Impede
            # que um executável renomeado para .jpg chegue ao storage.
            try:
                from PIL import Image

                upload.seek(0)
                Image.open(upload).verify()
            except Exception as error:  # noqa: BLE001 - qualquer falha invalida o arquivo
                raise forms.ValidationError(
                    f"“{upload.name}” não pôde ser lido como imagem."
                ) from error
            finally:
                upload.seek(0)

        return files


# ---------------------------------------------------------------------------
# Vistoria
# ---------------------------------------------------------------------------


class InspectionForm(forms.Form):
    """Checklist de entrada montado a partir dos itens já gravados.

    Os campos são criados dinamicamente para que o conjunto do checklist possa
    mudar no futuro sem reescrever o formulário.
    """

    fuel_level = forms.ChoiceField(
        label="Nível de combustível", choices=FuelLevel.choices, initial=FuelLevel.NOT_CHECKED
    )
    notes = forms.CharField(
        label="Observações gerais",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "opcional"}),
    )

    def __init__(self, *args, items=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.items = list(items or [])

        for item in self.items:
            self.fields[f"condition_{item.key}"] = forms.ChoiceField(
                label=item.label,
                choices=ItemCondition.choices,
                initial=item.condition,
                widget=forms.RadioSelect,
            )
            self.fields[f"note_{item.key}"] = forms.CharField(
                label=f"Observação — {item.label}",
                required=False,
                max_length=200,
                initial=item.note,
                widget=forms.TextInput(attrs={"placeholder": "observação"}),
            )

    def item_rows(self):
        """Pareia cada item do checklist com seus dois campos, para o template."""
        for item in self.items:
            yield item, self[f"condition_{item.key}"], self[f"note_{item.key}"]

    @property
    def conditions(self) -> dict:
        return {
            item.key: self.cleaned_data.get(f"condition_{item.key}") for item in self.items
        }

    @property
    def item_notes(self) -> dict:
        return {item.key: self.cleaned_data.get(f"note_{item.key}", "") for item in self.items}


# ---------------------------------------------------------------------------
# Saída e cancelamento
# ---------------------------------------------------------------------------


class DeliveryForm(forms.Form):
    """Registro da saída do veículo.

    ``entry_km`` chega pelo construtor porque a regra do KM depende dele: um
    valor menor não é bloqueado, mas passa a exigir justificativa.
    """

    delivered_at = forms.DateTimeField(label="Data/hora da saída", widget=LocalDateTimeInput())
    exit_km = forms.IntegerField(
        label="KM de saída",
        min_value=0,
        widget=forms.NumberInput(attrs={"inputmode": "numeric", "placeholder": "86214"}),
    )
    exit_notes = forms.CharField(
        label="Resumo do serviço e observação final",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "O que foi entregue ao cliente."}),
    )
    exit_km_justification = forms.CharField(
        label="Justificativa do KM",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 2, "placeholder": "Obrigatória se o KM de saída for menor que o de entrada."}
        ),
    )

    # Os três campos abaixo são opcionais de propósito: o cliente costuma estar
    # com pressa na retirada, e um campo obrigatório aqui viraria "..." digitado
    # só para o formulário passar.
    received_by_name = forms.CharField(
        label="Retirado por",
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Deixe vazio se foi o próprio cliente"}),
    )
    received_by_document = forms.CharField(
        label="Documento de quem retirou",
        required=False,
        max_length=30,
        widget=forms.TextInput(attrs={"placeholder": "CPF ou RG (opcional)"}),
    )
    signature = forms.CharField(label="Assinatura", required=False, widget=forms.HiddenInput())

    def __init__(self, *args, entry_km: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry_km = entry_km
        self.fields["exit_km"].help_text = f"KM de entrada: {entry_km}"
        if not self.is_bound:
            self.initial.setdefault("delivered_at", timezone.localtime())
            self.initial.setdefault("exit_km", entry_km)

    def clean_signature(self):
        """Converte a assinatura desenhada na tela em um PNG validado.

        O campo chega como data URL vinda de um ``<canvas>``. Nada do que o
        navegador manda é confiável, então o conteúdo é decodificado e aberto
        pelo Pillow antes de virar arquivo.
        """
        raw = (self.cleaned_data.get("signature") or "").strip()
        if not raw:
            return None

        prefix = "data:image/png;base64,"
        if not raw.startswith(prefix):
            raise forms.ValidationError("Assinatura em formato inesperado. Tente assinar novamente.")

        try:
            payload = base64.b64decode(raw[len(prefix) :], validate=True)
        except (binascii.Error, ValueError) as error:
            raise forms.ValidationError("Não foi possível ler a assinatura.") from error

        if len(payload) > 2 * 1024 * 1024:
            raise forms.ValidationError("Assinatura muito grande.")

        try:
            from PIL import Image

            Image.open(io.BytesIO(payload)).verify()
        except Exception as error:  # noqa: BLE001 - qualquer falha invalida o arquivo
            raise forms.ValidationError("A assinatura não é uma imagem válida.") from error

        return ContentFile(payload, name="assinatura.png")

    def clean(self):
        cleaned = super().clean()
        exit_km = cleaned.get("exit_km")
        justification = (cleaned.get("exit_km_justification") or "").strip()

        if exit_km is not None and exit_km < self.entry_km and not justification:
            self.add_error(
                "exit_km_justification",
                ValidationError(
                    f"KM de saída ({exit_km}) é inferior ao de entrada ({self.entry_km}). "
                    "Justifique para continuar."
                ),
            )
        return cleaned


class CancelOrderForm(forms.Form):
    cancellation_reason = forms.CharField(
        label="Motivo do cancelamento",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Por que esta OS está sendo cancelada."}),
    )

    def clean_cancellation_reason(self):
        reason = (self.cleaned_data.get("cancellation_reason") or "").strip()
        if not reason:
            raise forms.ValidationError("Informe o motivo do cancelamento.")
        return reason
