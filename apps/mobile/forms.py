"""Formulários enxutos do app mobile — só o essencial do primeiro contato."""

from django import forms

from apps.core.utils import normalize_phone
from apps.customers.models import Client
from apps.vehicles.models import Vehicle, normalize_plate, validate_plate
from apps.workorders.models import Priority


class MobileEntryForm(forms.Form):
    """KM, queixa e prioridade: o mínimo para abrir a OS no pátio."""

    entry_km = forms.IntegerField(
        label="KM do painel",
        min_value=0,
        widget=forms.NumberInput(
            attrs={
                "placeholder": "Ex.: 86210",
                "inputmode": "numeric",
                "class": "m-field-input",
            }
        ),
    )
    customer_complaint = forms.CharField(
        label="O que o cliente reclamou / pediu?",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Ex.: barulho na dianteira, luz acesa no painel, revisão…",
                "class": "m-textarea",
            }
        ),
        help_text="Anote com as palavras do cliente — a recepção detalha depois.",
    )
    priority = forms.ChoiceField(
        label="Prioridade",
        choices=(
            (Priority.NORMAL, "Normal"),
            (Priority.URGENT, "Urgente"),
        ),
        initial=Priority.NORMAL,
        widget=forms.RadioSelect(attrs={"class": "m-priority-input"}),
    )
    brought_by_name = forms.CharField(
        label="Quem trouxe o carro",
        required=False,
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Deixe em branco se for o próprio cliente",
                "class": "m-field-input",
                "autocomplete": "name",
            }
        ),
        help_text="Opcional — filho, motorista, funcionário, etc.",
    )

    def clean_customer_complaint(self):
        value = (self.cleaned_data.get("customer_complaint") or "").strip()
        if not value:
            raise forms.ValidationError("Descreva o que o cliente reclamou ou pediu.")
        return value

    def clean_brought_by_name(self):
        return " ".join((self.cleaned_data.get("brought_by_name") or "").split())


class MobileClientFields(forms.Form):
    """Dados básicos do cliente no primeiro contato."""

    name = forms.CharField(
        label="Nome do cliente",
        max_length=150,
        widget=forms.TextInput(
            attrs={"placeholder": "Nome completo", "class": "m-field-input", "autocomplete": "name"}
        ),
    )
    phone = forms.CharField(
        label="Telefone / WhatsApp",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "placeholder": "(13) 99999-9999",
                "inputmode": "tel",
                "class": "m-field-input",
                "autocomplete": "tel",
            }
        ),
        help_text="Principal canal de contato. Use o WhatsApp sempre que possível.",
    )
    phone_whatsapp = forms.CharField(
        label="WhatsApp (se for outro número)",
        required=False,
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Deixe em branco se for o mesmo",
                "inputmode": "tel",
                "class": "m-field-input",
            }
        ),
    )

    def clean_name(self):
        return " ".join((self.cleaned_data.get("name") or "").split())

    def clean_phone(self):
        digits = normalize_phone(self.cleaned_data.get("phone"))
        if len(digits) < 10:
            raise forms.ValidationError("Informe DDD e número. Ex.: (13) 99999-9999.")
        return digits

    def clean_phone_whatsapp(self):
        value = self.cleaned_data.get("phone_whatsapp")
        if not value:
            return ""
        digits = normalize_phone(value)
        if len(digits) < 10:
            raise forms.ValidationError("Informe DDD e número, ou deixe em branco.")
        return digits


class MobileVehicleFields(forms.Form):
    """Identificação rápida do carro — detalhes finos ficam no notebook."""

    plate = forms.CharField(
        label="Placa",
        max_length=10,
        widget=forms.TextInput(
            attrs={
                "placeholder": "ABC1D23",
                "autocapitalize": "characters",
                "autocomplete": "off",
                "class": "m-field-input m-field-input--plate",
            }
        ),
    )
    brand = forms.CharField(
        label="Marca",
        max_length=40,
        widget=forms.TextInput(attrs={"placeholder": "Chevrolet", "class": "m-field-input"}),
    )
    model = forms.CharField(
        label="Modelo",
        max_length=60,
        widget=forms.TextInput(attrs={"placeholder": "Onix", "class": "m-field-input"}),
    )
    color = forms.CharField(
        label="Cor",
        required=False,
        max_length=30,
        widget=forms.TextInput(attrs={"placeholder": "Prata", "class": "m-field-input"}),
    )
    model_year = forms.IntegerField(
        label="Ano",
        required=False,
        min_value=1950,
        max_value=2100,
        widget=forms.NumberInput(
            attrs={"placeholder": "2020", "inputmode": "numeric", "class": "m-field-input"}
        ),
    )

    def clean_plate(self):
        plate = normalize_plate(self.cleaned_data.get("plate"))
        validate_plate(plate)
        if Vehicle.objects.filter(plate=plate).exists():
            raise forms.ValidationError("Já existe um veículo com esta placa.")
        return plate


class MobileNewEntryForm(MobileClientFields, MobileEntryForm, MobileVehicleFields):
    """Cadastro completo de primeiro contato: cliente → queixa → veículo."""

    def __init__(self, *args, initial_plate="", **kwargs):
        super().__init__(*args, **kwargs)
        if initial_plate and not self.is_bound:
            self.fields["plate"].initial = initial_plate
        for name in ("name", "phone", "plate", "brand", "model", "entry_km", "customer_complaint"):
            self.fields[name].widget.attrs.setdefault("required", True)
        # Ordem mental do pátio: quem é → o que pediu → qual carro.
        self.order_fields(
            [
                "name",
                "phone",
                "phone_whatsapp",
                "customer_complaint",
                "entry_km",
                "priority",
                "brought_by_name",
                "plate",
                "brand",
                "model",
                "color",
                "model_year",
            ]
        )


class MobileReturningEntryForm(MobileEntryForm):
    """Cliente já cadastrado: confirma nome/telefone + KM, queixa e prioridade."""

    name = forms.CharField(
        label="Nome do cliente",
        max_length=150,
        widget=forms.TextInput(
            attrs={"placeholder": "Nome completo", "class": "m-field-input", "autocomplete": "name"}
        ),
        help_text="Confirme ou corrija o nome no cadastro.",
    )
    phone = forms.CharField(
        label="Telefone / WhatsApp",
        max_length=20,
        widget=forms.TextInput(
            attrs={"placeholder": "(13) 99999-9999", "inputmode": "tel", "class": "m-field-input"}
        ),
        help_text="Confirme ou atualize o telefone do cliente.",
    )

    def __init__(self, *args, client: Client | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if client and not self.is_bound:
            self.fields["name"].initial = client.name
            self.fields["phone"].initial = client.phone_whatsapp or client.phone
        self.order_fields(
            [
                "name",
                "phone",
                "customer_complaint",
                "entry_km",
                "priority",
                "brought_by_name",
            ]
        )

    def clean_name(self):
        value = " ".join((self.cleaned_data.get("name") or "").split())
        if not value:
            raise forms.ValidationError("Informe o nome do cliente.")
        return value

    def clean_phone(self):
        digits = normalize_phone(self.cleaned_data.get("phone"))
        if len(digits) < 10:
            raise forms.ValidationError("Informe DDD e número.")
        return digits
