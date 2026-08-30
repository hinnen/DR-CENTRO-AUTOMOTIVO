from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm

from .models import User


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
