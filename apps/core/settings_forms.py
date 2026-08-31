"""Formulários da aba Configurações."""

from django import forms

from apps.core.models import WorkshopSettings


class WorkshopPreferencesForm(forms.ModelForm):
    class Meta:
        model = WorkshopSettings
        fields = ["reception_can_create_mechanic", "auto_whatsapp_status_notify"]
        labels = {
            "reception_can_create_mechanic": "Recepção pode cadastrar mecânicos",
            "auto_whatsapp_status_notify": "Avisar cliente no WhatsApp ao mudar status",
        }
        help_texts = {
            "reception_can_create_mechanic": (
                "Desligado: só administradores criam mecânicos. "
                "Ligado: recepção também pode, pelo cadastro rápido da OS."
            ),
            "auto_whatsapp_status_notify": (
                "Quando ligado, ao mudar o status da OS o sistema abre o WhatsApp "
                "com a mensagem pronta para enviar ao cliente (wa.me — você confirma o envio)."
            ),
        }


class DemoPurgeForm(forms.Form):
    password = forms.CharField(
        label="Senha do administrador",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class SpreadsheetUploadForm(forms.Form):
    arquivo = forms.FileField(label="Planilha Excel (.xlsx)")
