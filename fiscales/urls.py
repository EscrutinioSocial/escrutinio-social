# -*- coding: utf-8 -*-
from django.conf.urls import url
from . import views


urlpatterns = [
    url('^_autocomplete/s$', views.SeccionListView.as_view(), name='autocomplete-seccion'),
    url('^_autocomplete/c$', views.CircuitoListView.as_view(), name='autocomplete-circuito'),
    url('^_autocomplete/m$', views.MesaListView.as_view(), name='autocomplete-mesa'),

    url('^mis-datos$', views.MisDatos.as_view(), name='mis-datos'),
    url('^acta/$', views.realizar_siguiente_accion, name='siguiente-accion'),
    url('^acta/(?P<categoria_id>\d+)/(?P<mesa_numero>\d+)$',
        views.cargar_resultados, name='mesa-cargar-resultados'),
    
    url('^ub/acta/(?P<mesa_id>\d+)$', views.cargar_resultados_mesa_desde_ub, name='procesar-acta-mesa'),
    url('^acta-parcial/(?P<categoria_id>\d+)/(?P<mesa_numero>\d+)$',
        views.cargar_resultados, {'tipo': 'parcial'}, name='mesa-cargar-resultados-parciales'),

    url('^mesa/(?P<categoria_id>\d+)/(?P<mesa_numero>\d+)$',
         views.detalle_mesa_categoria, name='detalle-mesa-categoria'),

    url('^mis-datos/profile$', views.MisDatosUpdate.as_view(), name='mis-datos-update'),
    url('^mis-datos/password$', views.CambiarPassword.as_view(), name='cambiar-password'),
    url('^_confirmar/(?P<fiscal_id>\d+)$', views.confirmar_fiscal, name='confirmar-fiscal'),
    url(r'^carga-simultanea/(?P<mesa>[^/]+)/(?P<categoria>.+)$', views.carga_simultanea, name="carga-simultanea"),
    url(r'^post-reportar-problema/(?P<mesa>\w+)$', views.post_reportar_problema, name="post-reportar-problema"),
    url(r'^bienvenido$', views.bienvenido, name="bienvenido"),
]
