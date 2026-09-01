from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from apps.core.bug_report_views import api_bug_report_criar, api_bug_report_status
from apps.core.media import serve_media
from apps.core.views import healthz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("healthz/", healthz),
    path("api/bug-report/", api_bug_report_criar, name="api_bug_report_criar"),
    path("api/bug-report/<int:pk>/status/", api_bug_report_status, name="api_bug_report_status"),
    path("configuracoes/", include("apps.core.urls")),
    path("admin/", admin.site.urls),
    path("conta/", include("apps.accounts.urls")),
    path("clientes/", include("apps.customers.urls")),
    path("veiculos/", include("apps.vehicles.urls")),
    path("m/", include("apps.mobile.urls")),
    path("", include("apps.workorders.urls")),
    path("", include("apps.dashboard.urls")),
    # Sempre disponível (DEBUG True ou False). Fotos exigem login.
    re_path(r"^media/(?P<path>.*)$", serve_media, name="media"),
]

handler403 = "apps.core.views.error_403"
handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"

admin.site.site_header = f"{settings.WORKSHOP_NAME} — administração"
admin.site.site_title = settings.WORKSHOP_NAME
admin.site.index_title = "Manutenção de dados"
