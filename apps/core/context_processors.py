from django.conf import settings


def workshop(request):
    return {"workshop_name": settings.WORKSHOP_NAME}


def whatsapp_auto_open(request):
    """Abre wa.me uma vez após redirect (ex.: entrega com aviso ao cliente)."""
    if not hasattr(request, "session"):
        return {"auto_open_whatsapp_url": ""}
    url = request.session.pop("open_whatsapp_url", "") or ""
    return {"auto_open_whatsapp_url": url}
