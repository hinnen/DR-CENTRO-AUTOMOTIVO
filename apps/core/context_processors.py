from django.conf import settings


def workshop(request):
    return {"workshop_name": settings.WORKSHOP_NAME}


def whatsapp_auto_open(request):
    """Abre wa.me uma vez após redirect (ex.: entrega com aviso ao cliente)."""
    if not hasattr(request, "session"):
        return {"auto_open_whatsapp_url": ""}
    url = request.session.pop("open_whatsapp_url", "") or ""
    return {"auto_open_whatsapp_url": url}


def brand_share(request):
    """URLs absolutas para WhatsApp / Open Graph (domínio canônico)."""
    configured = (getattr(settings, "PUBLIC_BASE_URL", "") or "").rstrip("/")
    if configured:
        base = configured
    elif hasattr(request, "get_host"):
        scheme = "https" if request.is_secure() else "http"
        base = f"{scheme}://{request.get_host()}"
    else:
        base = ""

    version = getattr(settings, "OG_IMAGE_VERSION", "3")
    og_image = f"{base}/static/img/og-share.png?v={version}" if base else ""
    return {
        "public_base_url": base,
        "og_image_url": og_image,
        "og_image_version": version,
    }
