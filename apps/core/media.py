"""Servir arquivos de mídia (fotos, assinaturas) com autenticação.

Com ``DEBUG=False`` o ``django.conf.urls.static.static`` não monta rota nenhuma —
toda URL ``/media/...`` vira 404, mesmo com o arquivo no disco. Esta view fica
sempre registrada e só entrega para quem está logado (fotos da oficina não são
públicas).
"""

from pathlib import Path

from django.conf import settings
from django.http import Http404
from django.views.static import serve


def serve_media(request, path: str):
    """Entrega um arquivo sob ``MEDIA_ROOT``.

    Anônimo recebe 404 (não redirect de login): a tag ``<img>`` não pode
    receber HTML de login no lugar da imagem.
    """
    if not request.user.is_authenticated:
        raise Http404()

    root = Path(settings.MEDIA_ROOT)
    # Impede path traversal (../../etc/passwd) mesmo com o serve() do Django.
    try:
        full = (root / path).resolve(strict=False)
        full.relative_to(root.resolve())
    except (OSError, ValueError):
        raise Http404() from None

    return serve(request, path, document_root=str(root))
