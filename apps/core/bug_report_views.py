"""Reportar bug — API + lista para administradores."""

from __future__ import annotations

import base64
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.bug_report_services import notificar_report, sanitizar_print_base64
from apps.core.models import BugReport

logger = logging.getLogger(__name__)


def _require_admin(user):
    if not user.can_manage_users:
        return HttpResponseForbidden("Somente administradores acessam os bugs reportados.")


def _usuario_nome(request, data: dict) -> str:
    informado = (data.get("usuario_nome") or "").strip()
    if informado:
        return informado[:120]
    if request.user.is_authenticated:
        return request.user.display_name[:120]
    return ""


@login_required
@require_POST
def api_bug_report_criar(request):
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "erro": "JSON inválido."}, status=400)

    aconteceu = (data.get("o_que_aconteceu") or "").strip()
    if len(aconteceu) < 3:
        return JsonResponse({"ok": False, "erro": "Escreva o que aconteceu (mín. 3 letras)."}, status=400)

    esperava = (data.get("o_que_esperava") or "").strip()
    print_b64, print_mime = sanitizar_print_base64(data.get("print_base64") or "")
    app_ctx = (data.get("app_context") or "").strip().lower()
    if app_ctx not in {BugReport.APP_DESKTOP, BugReport.APP_MOBILE}:
        app_ctx = BugReport.APP_MOBILE if "/m/" in (data.get("url_pagina") or "") else BugReport.APP_DESKTOP

    report = BugReport.objects.create(
        o_que_aconteceu=aconteceu[:8000],
        o_que_esperava=esperava[:4000],
        usuario_nome=_usuario_nome(request, data),
        usuario=request.user,
        device_id=(data.get("device_id") or "").strip()[:64],
        dispositivo_nome=(data.get("dispositivo_nome") or "").strip()[:80],
        app_context=app_ctx,
        url_pagina=(data.get("url_pagina") or "")[:500],
        versao_app=(data.get("versao_app") or "").strip()[:32],
        user_agent=(data.get("user_agent") or request.META.get("HTTP_USER_AGENT") or "")[:400],
        tela=(data.get("tela") or "")[:40],
        print_base64=print_b64,
        print_mime=print_mime,
    )
    avisos = notificar_report(report, request)
    return JsonResponse({"ok": True, "id": report.pk, "mensagem": f"Recebido — #{report.pk}", "avisos": avisos})


@login_required
@ensure_csrf_cookie
@never_cache
@require_GET
def bug_reports_lista_view(request):
    denied = _require_admin(request.user)
    if denied:
        return denied
    qs = BugReport.objects.all()[:200]
    novos = BugReport.objects.filter(status=BugReport.STATUS_NOVO).count()
    return render(
        request,
        "core/bug_reports_lista.html",
        {"reports": qs, "total": BugReport.objects.count(), "novos": novos},
    )


@login_required
@never_cache
@require_GET
def bug_report_detalhe_view(request, pk: int):
    denied = _require_admin(request.user)
    if denied:
        return denied
    report = get_object_or_404(BugReport, pk=pk)
    print_url = ""
    if (report.print_base64 or "").strip():
        try:
            print_url = request.build_absolute_uri(reverse("core:bug_report_print", kwargs={"pk": report.pk}))
        except Exception:
            print_url = reverse("core:bug_report_print", kwargs={"pk": report.pk})
    quando = report.created_at.strftime("%d/%m/%Y %H:%M") if report.created_at else ""
    prompt_payload = {
        "pk": report.pk,
        "aconteceu": (report.o_que_aconteceu or "").strip(),
        "esperava": (report.o_que_esperava or "").strip(),
        "quem": (report.usuario_nome or "").strip(),
        "dispositivo": (report.dispositivo_nome or "").strip(),
        "contexto": report.get_app_context_display() if report.app_context else "",
        "url": (report.url_pagina or "").strip(),
        "versao": (report.versao_app or "").strip(),
        "quando": quando,
        "status": (report.status or "").strip(),
        "tela": (report.tela or "").strip(),
        "print_url": print_url,
    }
    return render(
        request,
        "core/bug_report_detalhe.html",
        {"report": report, "bug_cursor_prompt": prompt_payload},
    )


@login_required
@require_http_methods(["POST"])
def api_bug_report_status(request, pk: int):
    denied = _require_admin(request.user)
    if denied:
        return denied
    report = get_object_or_404(BugReport, pk=pk)
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        data = {}
    st = (data.get("status") or "").strip().lower()
    valid = {c[0] for c in BugReport.STATUS_CHOICES}
    if st not in valid:
        return JsonResponse({"ok": False, "erro": "Status inválido."}, status=400)
    report.status = st
    report.save(update_fields=["status"])
    return JsonResponse({"ok": True, "id": report.pk, "status": report.status})


@login_required
@require_GET
def bug_report_print_view(request, pk: int):
    denied = _require_admin(request.user)
    if denied:
        return denied
    report = get_object_or_404(BugReport, pk=pk)
    if not (report.print_base64 or "").strip():
        return HttpResponse("Sem print.", status=404, content_type="text/plain")
    try:
        raw = base64.b64decode(report.print_base64)
    except Exception:
        return HttpResponse("Print inválido.", status=400, content_type="text/plain")
    mime = (report.print_mime or "image/jpeg").strip() or "image/jpeg"
    return HttpResponse(raw, content_type=mime)
