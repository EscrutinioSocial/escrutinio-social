# -*- coding: utf-8 -*-
from django.conf.urls import url
from . import views, data_views
from fancy_cache import cache_page
from django.contrib.auth.decorators import login_required
from elecciones.resultados import Sumarizador

cached = cache_page(300)

urlpatterns = [
    url('^escuelas.geojson$', cached(
        views.LugaresVotacionGeoJSON.as_view()), name='geojson'),
    url('^escuelas/(?P<pk>\d+)$',
        views.EscuelaDetailView.as_view(), name='detalle_escuela'),
    url('^mapa/$', login_required(cached(views.Mapa.as_view())), name='mapa'),
    url(
        '^resultados-parciales-sin-confirmar/(?P<pk>\d+)?$',
        views.ResultadosCategoria.as_view(),
        {'status': 'psc'},
        name='resultados-categoria'
    ),
    url(
        '^resultados-parciales-confirmados/(?P<pk>\d+)?$',
        views.ResultadosCategoria.as_view(),
        {'status': 'pc'},
        name='resultados-parciales-confirmados'
    ),
    url(
        '^resultados-totales-sin-confirmar/(?P<pk>\d+)?$',
        views.ResultadosCategoria.as_view(),
        {
            'opciones_a_considerar': Sumarizador.OPCIONES_A_CONSIDERAR.todas,
            'tipo_de_agregacion': Sumarizador.TIPOS_DE_AGREGACIONES.todas_las_cargas
        },

        name='resultados-totales-sin-confirmar'
    ),
    url(
        '^resultados-totales-confirmados/(?P<pk>\d+)?$',
        views.ResultadosCategoria.as_view(),
        {'status': 'tc'},
        name='resultados-totales-confirmados'
    ),

    url(r'^resultados-parciales-(?P<slug_categoria>[\w-]+).(?P<filetype>csv|xls)$',
        data_views.resultado_parcial_categoria, name='resultado-parcial-categoria'),

    # url(r'^fiscal_mesa/', views.fiscal_mesa, name='fiscal_mesa'),
]
