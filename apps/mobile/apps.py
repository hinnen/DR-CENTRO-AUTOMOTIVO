from django.apps import AppConfig


class MobileConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mobile"
    verbose_name = "App de vistoria"

    def ready(self):
        """Warmup ONNX em background — default OFF (Starter Render → 502 se bloquear boot)."""
        import os
        import threading

        if os.getenv("PLATE_OCR_WARMUP", "0") != "1":
            return

        def _warmup():
            try:
                from .plate_ocr import warmup_engine

                warmup_engine()
            except Exception:
                import logging

                logging.getLogger(__name__).warning(
                    "Warmup do platerec falhou — 1ª leitura de placa pode demorar.",
                    exc_info=True,
                )

        threading.Thread(target=_warmup, name="platerec-warmup", daemon=True).start()
