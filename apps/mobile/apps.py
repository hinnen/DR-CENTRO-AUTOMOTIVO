from django.apps import AppConfig


class MobileConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mobile"
    verbose_name = "App de vistoria"

    def ready(self):
        """Warmup do ONNX em background — nunca bloqueia o boot do Gunicorn.

        No plano Starter do Render, carregar platerec no ready() sincronamente
        estoura memória/timeout do health check → 502. Opt-in via PLATE_OCR_WARMUP=1.
        """
        import os
        import threading

        from django.conf import settings

        # Default OFF em produção (Starter). Liga só com PLATE_OCR_WARMUP=1.
        default = "0"
        if os.getenv("PLATE_OCR_WARMUP", default) != "1":
            return
        if os.environ.get("RUN_MAIN") == "false":
            return  # evita double-load no runserver reloader

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
