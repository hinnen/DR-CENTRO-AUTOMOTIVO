"""Middleware do núcleo — health check do Render precisa responder 200 sem rodeio."""

from django.http import HttpResponse

_HEALTHZ = frozenset({"/healthz", "/healthz/"})


class HealthCheckMiddleware:
    """Responde /healthz antes de SSL redirect, ALLOWED_HOSTS e o resto do stack.

    Sem isso, o deploy no Render marca falha (~16 min) e o site fica em 502
    mesmo com o Gunicorn no ar.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in _HEALTHZ:
            return HttpResponse("ok", content_type="text/plain")
        return self.get_response(request)
