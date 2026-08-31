from django import forms

from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm

from .models import Role, User


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Usuário ou senha incorretos.",
        "inactive": "Este usuário está inativo.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"autofocus": True, "autocomplete": "username", "placeholder": "Seu usuário"}
        )
        self.fields["username"].label = "Usuário"
        self.fields["password"].widget.attrs.update(
            {"autocomplete": "current-password", "placeholder": "Sua senha"}
        )
        self.fields["password"].label = "Senha"


class UserCreateForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone", "role")


class UserUpdateForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone", "role", "is_active")


class OperationalUserCreateForm(forms.Form):
    name = forms.CharField(
        label="Nome completo",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Maria Silva"}),
    )
    username = forms.CharField(
        label="Usuário",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "username", "placeholder": "maria"}),
    )
    role = forms.ChoiceField(
        label="Perfil",
        choices=[
            (Role.ADMIN, Role.ADMIN.label),
            (Role.RECEPTION, Role.RECEPTION.label),
            (Role.MECHANIC, Role.MECHANIC.label),
        ],
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
        help_text="Senha de login — exatamente 4 números.",
    )
    phone = forms.CharField(
        label="Telefone",
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "opcional"}),
    )


class UserPinResetForm(forms.Form):
    pin = forms.CharField(
        label="Novo PIN",
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
    )
