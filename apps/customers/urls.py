from django.urls import path

from . import views

app_name = "customers"

urlpatterns = [
    path("", views.ClientListView.as_view(), name="list"),
    path("novo/", views.ClientCreateView.as_view(), name="create"),
    path("buscar-telefone/", views.phone_lookup, name="phone_lookup"),
    path("buscar/", views.client_lookup, name="client_lookup"),
    path("<uuid:uuid>/", views.ClientDetailView.as_view(), name="detail"),
    path("<uuid:uuid>/editar/", views.ClientUpdateView.as_view(), name="update"),
]
