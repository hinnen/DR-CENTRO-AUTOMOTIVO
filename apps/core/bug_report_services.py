"""Bug report — sanitização de print e aviso opcional por e-mail."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.mail import send_mail

if TYPE_CHECKING:
    from apps.core.models import BugReport

logger = logging.getLogger(__name__)

_PRINT_MAX_CHARS = 1_200_000


def sanitizar_print_base64(raw: str) -> tuple[str, str]:
    s = (raw or "").strip()
    mime = "image/jpeg"
    if not s:
        return "", mime
    if s.startswith("data:") and ";base64," in s:
        head, _, b64 = s.partition(";base64,")
        mime = head.replace("data:", "").strip() or mime
        s = b64.strip()
    if len(s) > _PRINT_MAX_CHARS:
        s = s[:_PRINT_MAX_CHARS]
    return s, mime


def _url_lista(request=None) -> str:
    path = "/configuracoes/bugs/"
    if request is not None:
        try:
            return request.build_absolute_uri(path)
        except Exception:
            pass
    base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").rstrip("/")
    if base:
        return f"{base}{path}"
    return path


def _mensagem(report: BugReport, request=None) -> str:
    trecho = (report.o_que_aconteceu or "").strip().replace("\n", " ")
    if len(trecho) > 180:
        trecho = trecho[:177] + "…"
    ctx = report.get_app_context_display() if report.app_context else "?"
    dispositivo = (report.dispositivo_nome or report.device_id[:8] or "?").strip()
    return (
        f"🐛 DR Oficina bug #{report.pk}\n"
        f"Quem: {report.usuario_nome or '?'}\n"
        f"Onde: {dispositivo} · {ctx}\n"
        f"Tela: {(report.url_pagina or '')[:120]}\n"
        f"{trecho}\n"
        f"Lista: {_url_lista(request)}"
    )


def notificar_email(report: BugReport, request=None) -> bool:
    destino = (getattr(settings, "BUG_REPORT_EMAIL", "") or "").strip()
    if not destino:
        return False
    host = (getattr(settings, "EMAIL_HOST", "") or "").strip()
    if not host:
        return False
    remetente = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip() or destino
    try:
        send_mail(
            subject=f"[DR Oficina] Bug #{report.pk} — {report.usuario_nome or '?'}",
            message=_mensagem(report, request),
            from_email=remetente,
            recipient_list=[destino],
            fail_silently=False,
        )
        report.notificado_email = True
        report.save(update_fields=["notificado_email"])
        return True
    except Exception:
        logger.exception("Bug #%s e-mail falhou", report.pk)
        return False


def notificar_report(report: BugReport, request=None) -> dict:
    return {"email": notificar_email(report, request)}
