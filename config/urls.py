from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core.views import healthz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("conta/", include("apps.accounts.urls")),
    path("clientes/", include("apps.customers.urls")),
    path("veiculos/", include("apps.vehicles.urls")),
    path("m/", include("apps.mobile.urls")),
    path("", include("apps.workorders.urls")),
    path("", include("apps.dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = "apps.core.views.error_403"
handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"

admin.site.site_header = f"{settings.WORKSHOP_NAME} — administração"
admin.site.site_title = settings.WORKSHOP_NAME
admin.site.index_title = "Manutenção de dados"
