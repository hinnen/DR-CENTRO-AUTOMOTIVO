from django.urls import path

from . import views

app_name = "mobile"

urlpatterns = [
    path("", views.home, name="home"),
    path("perfil/", views.profile, name="profile"),
    path("sair/", views.logout_view, name="logout"),
    path("entrada/", views.entry_start, name="entry_start"),
    path("entrada/buscar-placa/", views.entry_plate_lookup, name="entry_plate_lookup"),
    path("entrada/ler-placa/", views.entry_read_plate, name="entry_read_plate"),
    path("entrada/novo/", views.entry_new, name="entry_new"),
    path("entrada/veiculo/<uuid:uuid>/", views.entry_existing, name="entry_existing"),
    path("os/<uuid:uuid>/", views.inspection, name="inspection"),
    path("os/<uuid:uuid>/fotos/", views.upload_photos, name="upload_photos"),
    path(
        "os/<uuid:uuid>/fotos/<int:photo_id>/remover/",
        views.remove_photo,
        name="remove_photo",
    ),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
]
