# -*- coding: utf-8 -*-
from django.conf.urls import url
from . import views


urlpatterns = [
    url('^mis-datos$', views.MisDatos.as_view(), name='mis-datos'),
    url('^acta/$', views.realizar_siguiente_accion, name='siguiente-accion'),
    url('^acta/(?P<categoria_id>\d+)/(?P<mesa_numero>\d+)$',
        views.cargar_resultados, name='mesa-cargar-resultados'),

    url('^chequear$',
        views.chequear_resultado, name='chequear-resultado'),

    url('^chequear/(?P<categoria_id>\d+)/(?P<mesa_numero>\d+)$',
        views.chequear_resultado_mesa, name='chequear-resultado-mesa'),

    url('^mis-datos/profile$', views.MisDatosUpdate.as_view(), name='mis-datos-update'),
    url('^mis-datos/password$', views.CambiarPassword.as_view(), name='cambiar-password'),
    url('^_confirmar/(?P<fiscal_id>\d+)$', views.confirmar_fiscal, name='confirmar-fiscal'),
    url(r'^post-cargar-resultados/(?P<mesa>\w+)/(?P<categoria>\w+)$', views.post_cargar_resultados, name="post-cargar-resultados"),
    url(r'^post-confirmar-resultados/(?P<mesa>\w+)$', views.post_confirmar_resultados, name="post-confirmar-resultados"),
]
