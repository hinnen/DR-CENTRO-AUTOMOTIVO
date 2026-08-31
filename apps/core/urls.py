from django.urls import path
from django.views.generic import RedirectView

from . import settings_views

app_name = "core"

urlpatterns = [
    path("", settings_views.settings_index, name="settings_index"),
    path("preferencias/", settings_views.settings_preferences, name="settings_preferences"),
    path(
        "mecanicos/",
        RedirectView.as_view(pattern_name="core:settings_users", permanent=True),
        name="settings_mechanics",
    ),
    path("usuarios/", settings_views.settings_users, name="settings_users"),
    path(
        "usuarios/<uuid:user_uuid>/pin/",
        settings_views.settings_user_pin,
        name="settings_user_pin",
    ),
    path("localizacoes/", settings_views.settings_locations, name="settings_locations"),
    path("planilhas/", settings_views.settings_spreadsheets, name="settings_spreadsheets"),
    path(
        "planilhas/download/",
        settings_views.settings_spreadsheet_download,
        name="settings_spreadsheet_download",
    ),
    path("exemplos/", settings_views.settings_demo, name="settings_demo"),
]
