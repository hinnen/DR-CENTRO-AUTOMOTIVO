from django.apps import AppConfig


class MobileConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mobile"
    verbose_name = "App de vistoria"

    def ready(self):
        # Não carregar platerec/ONNX no boot. Starter (512 MB) morre → 502.
        return
