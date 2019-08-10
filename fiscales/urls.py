# -*- coding: utf-8 -*-
from django.conf.urls import url
from . import views

urlpatterns = [
    url('^_autocomplete/d$', views.DistritoListView.as_view(), name='autocomplete-distrito'),
    url('^_autocomplete/s$', views.SeccionListView.as_view(), name='autocomplete-seccion'),
    url('^_autocomplete/c$', views.CircuitoListView.as_view(), name='autocomplete-circuito'),
    url('^_autocomplete/m$', views.MesaListView.as_view(), name='autocomplete-mesa'),

    url('^_autocomplete_simple/d$', views.DistritoSimpleListView.as_view(), name='autocomplete-distrito-simple'),
    url('^_autocomplete_simple/s$', views.SeccionSimpleListView.as_view(), name='autocomplete-seccion-simple'),

    url('^mis-datos$', views.MisDatos.as_view(), name='mis-datos'),
    url('^referidos$', views.referidos, name='referidos'),
    url('^siguiente/$', views.realizar_siguiente_accion, name='siguiente-accion'),

    url('^ub/carga/(?P<mesa_id>\d+)$', views.cargar_desde_ub, name='procesar-acta-mesa'),
    url('^carga/(?P<mesacategoria_id>\d+)$', views.carga, name='carga-total'),
    url('^carga-parcial/(?P<mesacategoria_id>\d+)$', views.carga, {'tipo': 'parcial'}, name='carga-parcial'),
    url(r'^carga/(?P<mesacategoria_id>\d+)/problema$', views.ReporteDeProblemaCreateView.as_view(), name='problema'),

    url('^mesa/(?P<categoria_id>\d+)/(?P<mesa_numero>\d+)$',
        views.detalle_mesa_categoria, name='detalle-mesa-categoria'),

    url('^mis-datos/profile$', views.MisDatosUpdate.as_view(), name='mis-datos-update'),
    url('^mis-datos/password$', views.CambiarPassword.as_view(), name='cambiar-password'),
    url('^_confirmar/(?P<fiscal_id>\d+)$', views.confirmar_fiscal, name='confirmar-fiscal'),
    url(r'^bienvenido$', views.bienvenido, name="bienvenido"),
]
