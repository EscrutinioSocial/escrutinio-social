# -*- coding: utf-8 -*-
from django.urls import re_path
from . import views

urlpatterns = [
    re_path(
        "^_autocomplete/d$",
        views.DistritoListView.as_view(),
        name="autocomplete-distrito",
    ),
    re_path(
        "^_autocomplete/s$",
        views.SeccionListView.as_view(),
        name="autocomplete-seccion",
    ),
    re_path(
        "^_autocomplete/c$",
        views.CircuitoListView.as_view(),
        name="autocomplete-circuito",
    ),
    re_path(
        "^_autocomplete/m$", views.MesaListView.as_view(), name="autocomplete-mesa"
    ),
    re_path(
        "^_autocomplete_simple/d$",
        views.DistritoSimpleListView.as_view(),
        name="autocomplete-distrito-simple",
    ),
    re_path(
        "^_autocomplete_simple/s$",
        views.SeccionSimpleListView.as_view(),
        name="autocomplete-seccion-simple",
    ),
    re_path("^mis-datos$", views.MisDatos.as_view(), name="mis-datos"),
    re_path("^referidos$", views.referidos, name="referidos"),
    re_path("^siguiente/$", views.realizar_siguiente_accion, name="siguiente-accion"),
    re_path(
        r"^ub/carga/(?P<mesa_id>\d+)$", views.cargar_desde_ub, name="cargar-desde-ub"
    ),
    re_path(r"^carga/(?P<mesacategoria_id>\d+)$", views.carga, name="carga-total"),
    re_path(
        r"^carga-parcial/(?P<mesacategoria_id>\d+)$",
        views.carga,
        {"tipo": "parcial"},
        name="carga-parcial",
    ),
    re_path(
        r"^carga/(?P<mesacategoria_id>\d+)/problema$",
        views.ReporteDeProblemaCreateView.as_view(),
        name="problema",
    ),
    re_path(
        r"^mesa/(?P<categoria_id>\d+)/(?P<mesa_numero>\d+)$",
        views.detalle_mesa_categoria,
        name="detalle-mesa-categoria",
    ),
    re_path(
        "^mis-datos/profile$", views.MisDatosUpdate.as_view(), name="mis-datos-update"
    ),
    re_path(
        "^mis-datos/password$", views.CambiarPassword.as_view(), name="cambiar-password"
    ),
    re_path(
        r"^_confirmar/(?P<fiscal_id>\d+)$",
        views.confirmar_fiscal,
        name="confirmar-fiscal",
    ),
    re_path(r"^bienvenido$", views.bienvenido, name="bienvenido"),
]
