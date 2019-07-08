# -*- coding: utf-8 -*-
from django.conf.urls import url
from . import views


urlpatterns = [
    url('^_autocomplete/s$', views.SeccionListView.as_view(), name='autocomplete-seccion'),
    url('^_autocomplete/c$', views.CircuitoListView.as_view(), name='autocomplete-circuito'),

    url('^mis-datos$', views.MisDatos.as_view(), name='mis-datos'),
    url('^acta/$', views.elegir_acta_a_cargar, name='elegir-acta-a-cargar'),
    url('^acta/(?P<categoria_id>\d+)/(?P<mesa_numero>\d+)$',
        views.cargar_resultados, name='mesa-cargar-resultados'),

    url('^chequear$',
        views.chequear_resultado, name='chequear-resultado'),

    url('^chequear/(?P<categoria_id>\d+)/(?P<mesa_numero>\d+)$',
        views.chequear_resultado_mesa, name='chequear-resultado-mesa'),

    url('^mis-datos/profile$', views.MisDatosUpdate.as_view(), name='mis-datos-update'),
    url('^mis-datos/password$', views.CambiarPassword.as_view(), name='cambiar-password'),
    url('^_confirmar/(?P<fiscal_id>\d+)$', views.confirmar_fiscal, name='confirmar-fiscal'),
]
