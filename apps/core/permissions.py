"""Mixins e decorators de permissão.

Toda checagem acontece no backend. O template pode esconder um botão,
mas nunca é a fonte da autorização.
"""

from functools import wraps

from django.core.exceptions import PermissionDenied


class RoleRequiredMixin:
    """Exige que ``request.user`` satisfaça ``user_test``.

    Views concretas sobrescrevem ``user_test`` ou definem ``required_capability``
    com o nome de uma property booleana do User.
    """

    required_capability: str | None = None

    def user_test(self, user) -> bool:
        if self.required_capability is None:
            return True
        return bool(getattr(user, self.required_capability, False))

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Faça login para continuar.")
        if not self.user_test(request.user):
            raise PermissionDenied("Seu perfil não tem acesso a esta ação.")
        return super().dispatch(request, *args, **kwargs)


def capability_required(capability: str):
    """Protege views baseadas em função exigindo uma capability do User."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated or not getattr(user, capability, False):
                raise PermissionDenied("Seu perfil não tem acesso a esta ação.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
