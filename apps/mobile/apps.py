from django.apps import AppConfig


class MobileConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mobile"
    verbose_name = "App de vistoria"

    def ready(self):
        import os

        from django.conf import settings

        if os.getenv("PLATE_OCR_WARMUP", "1" if not settings.DEBUG else "0") != "1":
            return
        try:
            from .plate_ocr import warmup_engine

            warmup_engine()
        except Exception:
            import logging

            logging.getLogger(__name__).warning(
                "Warmup do platerec falhou — 1ª leitura de placa pode demorar.",
                exc_info=True,
            )
