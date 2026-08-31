"""Middleware do núcleo — health check do Render precisa responder 200 sem rodeio."""

import re

from django.http import HttpResponse
from django.shortcuts import render

_HEALTHZ = frozenset({"/healthz", "/healthz/"})

# Crawlers de preview (WhatsApp, Facebook, etc.) — não redirecionar / para login.
_SOCIAL_BOT_RE = re.compile(
    r"facebookexternalhit|Facebot|WhatsApp|Twitterbot|LinkedInBot|"
    r"Slackbot|Discordbot|TelegramBot|SkypeUriPreview|Googlebot",
    re.IGNORECASE,
)


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


class SocialPreviewMiddleware:
    """Entrega HTML com og:image em `/` para bots — sem 302 para o login.

    O WhatsApp às vezes não segue o redirect e cacheia preview sem ícone no
    domínio custom. Render e .com passam a responder 200 com a mesma meta.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in {"/", ""} and request.method == "GET":
            ua = request.META.get("HTTP_USER_AGENT", "")
            if _SOCIAL_BOT_RE.search(ua):
                return render(request, "core/social_preview.html", status=200)
        return self.get_response(request)
