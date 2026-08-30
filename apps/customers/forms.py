from django import forms

from apps.core.utils import normalize_phone, only_digits

from .models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["name", "phone", "phone_whatsapp", "email", "cpf_cnpj", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Nome completo", "autofocus": True}),
            "phone": forms.TextInput(attrs={"placeholder": "(13) 99999-9999", "inputmode": "tel"}),
            "phone_whatsapp": forms.TextInput(
                attrs={"placeholder": "Só se for diferente do telefone", "inputmode": "tel"}
            ),
            "email": forms.EmailInput(attrs={"placeholder": "opcional"}),
            "cpf_cnpj": forms.TextInput(attrs={"placeholder": "opcional", "inputmode": "numeric"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "opcional"}),
        }

    def clean_phone(self):
        digits = normalize_phone(self.cleaned_data.get("phone"))
        if len(digits) < 10:
            raise forms.ValidationError("Informe DDD e número. Exemplo: (13) 99999-9999.")
        return digits

    def clean_phone_whatsapp(self):
        value = self.cleaned_data.get("phone_whatsapp")
        if not value:
            return ""
        digits = normalize_phone(value)
        if len(digits) < 10:
            raise forms.ValidationError("Informe DDD e número, ou deixe em branco.")
        return digits

    def clean_cpf_cnpj(self):
        value = self.cleaned_data.get("cpf_cnpj")
        if not value:
            return ""
        digits = only_digits(value)
        if len(digits) not in (11, 14):
            raise forms.ValidationError("CPF deve ter 11 dígitos e CNPJ 14, ou deixe em branco.")
        return digits
