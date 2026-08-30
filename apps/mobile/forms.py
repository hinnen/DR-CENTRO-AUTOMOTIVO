"""Formulários enxutos do app mobile — só o essencial do primeiro contato."""

from django import forms

from apps.core.utils import normalize_phone
from apps.customers.models import Client
from apps.vehicles.models import Vehicle, normalize_plate, validate_plate


class MobileEntryForm(forms.Form):
    """KM e queixa: o mínimo para abrir a OS no pátio."""

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
        label="Queixa / motivo da visita",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "O que o cliente relatou?",
                "class": "m-textarea",
            }
        ),
    )

    def clean_customer_complaint(self):
        value = (self.cleaned_data.get("customer_complaint") or "").strip()
        if not value:
            raise forms.ValidationError("Descreva o que o cliente relatou.")
        return value


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


class MobileNewEntryForm(MobileClientFields, MobileVehicleFields, MobileEntryForm):
    """Cadastro completo de primeiro contato: cliente + carro + entrada."""

    def __init__(self, *args, initial_plate="", **kwargs):
        super().__init__(*args, **kwargs)
        if initial_plate and not self.is_bound:
            self.fields["plate"].initial = initial_plate
        for name in ("name", "phone", "plate", "brand", "model", "entry_km", "customer_complaint"):
            self.fields[name].widget.attrs.setdefault("required", True)


class MobileReturningEntryForm(MobileEntryForm):
    """Cliente já cadastrado: só KM, queixa e confirmação de telefone."""

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
            self.fields["phone"].initial = client.phone_whatsapp or client.phone

    def clean_phone(self):
        digits = normalize_phone(self.cleaned_data.get("phone"))
        if len(digits) < 10:
            raise forms.ValidationError("Informe DDD e número.")
        return digits
