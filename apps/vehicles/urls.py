from django.urls import path

from . import views

app_name = "vehicles"

urlpatterns = [
    path("<uuid:uuid>/", views.VehicleDetailView.as_view(), name="detail"),
    path("<uuid:uuid>/editar/", views.VehicleUpdateView.as_view(), name="update"),
]
