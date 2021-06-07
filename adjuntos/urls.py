from django.urls import re_path

from . import views

urlpatterns = [
    re_path(
        r"^(?P<attachment_id>\d+)/$",
        views.IdentificacionCreateView.as_view(),
        name="asignar-mesa",
    ),
    re_path(
        r"^(?P<attachment_id>\d+)/problema$",
        views.ReporteDeProblemaCreateView.as_view(),
        name="asignar-problema",
    ),
    re_path(
        r"^(?P<attachment_id>\d+)/editar-foto$", views.editar_foto, name="editar-foto"
    ),
    re_path(
        r"^agregar$",
        views.AgregarAdjuntosPreidentificar.as_view(),
        name="agregar-adjuntos",
    ),
    re_path(
        r"^ub/(?P<attachment_id>\d+)/$",
        views.IdentificacionCreateViewDesdeUnidadBasica.as_view(),
        name="asignar-mesa-ub",
    ),
    re_path(
        r"^ub/agregar$",
        views.AgregarAdjuntosDesdeUnidadBasica.as_view(),
        name="agregar-adjuntos-ub",
    ),
    re_path(
        r"^agregar-adjuntos-csv/$",
        views.AgregarAdjuntosCSV.as_view(),
        name="agregar-adjuntos-csv",
    ),
    re_path(
        r"^status-importacion-csv/(?P<csv_id>\d+)$",
        views.status_importacion_csv,
        name="status-importacion-csv",
    ),
]
