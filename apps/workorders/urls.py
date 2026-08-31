from django.urls import path

from . import catalog_views, views

app_name = "workorders"

urlpatterns = [
    path("entrada/nova/", views.new_entry, name="new_entry"),
    path("entrada/nova/veiculo/", views.new_entry_vehicle, name="new_entry_vehicle"),
    path("entrada/buscar-placa/", views.plate_lookup, name="plate_lookup"),
    path("oficina/", views.WorkshopListView.as_view(), name="workshop"),
    path("historico/", views.HistoryListView.as_view(), name="history"),
    path("buscar/", views.global_search, name="search"),
    path("whatsapp/oficina/", views.whatsapp_picker, name="whatsapp_picker"),
    path("catalogo/mecanicos/painel/", catalog_views.quick_mechanic_panel, name="quick_mechanic_panel"),
    path("catalogo/mecanicos/rapido/", catalog_views.quick_mechanic_create, name="quick_mechanic_create"),
    path("catalogo/localizacoes/painel/", catalog_views.quick_location_panel, name="quick_location_panel"),
    path("catalogo/localizacoes/rapido/", catalog_views.quick_location_create, name="quick_location_create"),
    path("os/<uuid:uuid>/", views.ServiceOrderDetailView.as_view(), name="detail"),
    path("os/<uuid:uuid>/status/", views.change_status, name="change_status"),
    path("os/<uuid:uuid>/mover/", views.change_status_from_board, name="move"),
    path("os/<uuid:uuid>/mecanico/", views.change_mechanic_view, name="change_mechanic"),
    path("os/<uuid:uuid>/localizacao/", views.change_location_view, name="change_location"),
    path("os/<uuid:uuid>/previsao/", views.change_delivery_view, name="change_delivery"),
    path("os/<uuid:uuid>/diagnostico/", views.update_diagnosis_view, name="update_diagnosis"),
    # Serviços
    path("os/<uuid:uuid>/servicos/", views.add_task_view, name="add_task"),
    path(
        "os/<uuid:uuid>/servicos/<int:task_id>/<slug:action>/",
        views.task_action_view,
        name="task_action",
    ),
    # Fotos
    path("os/<uuid:uuid>/fotos/", views.upload_photos_view, name="upload_photos"),
    path("os/<uuid:uuid>/fotos/<int:photo_id>/remover/", views.remove_photo_view, name="remove_photo"),
    # Vistoria
    path("os/<uuid:uuid>/vistoria/", views.inspection_view, name="inspection"),
    # Encerramento
    path("os/<uuid:uuid>/finalizar/", views.finalize_view, name="finalize"),
    path("os/<uuid:uuid>/saida/", views.delivery_view, name="delivery"),
    path("os/<uuid:uuid>/cancelar/", views.cancel_view, name="cancel"),
]
