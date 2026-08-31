import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class MobileConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mobile"
    verbose_name = "App de vistoria"

    def ready(self):
        # Nunca aquecer OCR no boot do Starter (512 MB) — morre → 502.
        # Só se PLATE_OCR_WARMUP=1 (plano maior / PC local).
        from django.conf import settings

        if not getattr(settings, "PLATE_OCR_WARMUP", False):
            return
        if not getattr(settings, "ENABLE_PLATE_OCR", False):
            return
        try:
            from .plate_ocr import warmup_engine

            warmup_engine()
        except Exception:
            logger.exception("Warmup OCR de placa falhou (seguindo sem modelo pré-carregado)")
