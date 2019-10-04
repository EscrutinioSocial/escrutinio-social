# -*- coding: utf-8 -*-
from django.conf.urls import url
from . import views, data_views
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_page

cached = cache_page(300)

urlpatterns = [
    url('^escuelas.geojson$', cached(
        views.LugaresVotacionGeoJSON.as_view()), name='geojson'),
    url(r'^escuelas/(?P<pk>\d+)$',
        views.EscuelaDetailView.as_view(), name='detalle_escuela'),
    url('^mapa/$', login_required(cached(views.Mapa.as_view())), name='mapa'),
    url(
        r'^avance_carga/(?P<pk>\d+)?$',
        views.AvanceDeCargaCategoria.as_view(),
        name='avance-carga'
    ),
    url(
        r'^resultados-nuevo-menu/(?P<categoria_id>\d+)?$',
        views.menu_lateral_resultados,
        name='resultados-nuevo-menu'
    ),
    url(
        r'^resultados/(?P<pk>\d+)?$',
        cache_page(0)(views.ResultadosCategoria.as_view()),
        name='resultados-categoria'
    ),
    url(
        r'^resultados-cuerpo-central/(?P<pk>\d+)?$',
        views.ResultadosCategoriaCuerpoCentral.as_view(),
        name='resultados-categoria-cuerpo-central'
    ),
    url(
        r'^resultados/mesas_circuito/(?P<pk>\d+)?$',
        views.MesasDeCircuito.as_view(),
        name='mesas-circuito'
    ),
    url(
        r'^resultados-parciales-(?P<slug_categoria>[\w-]+).(?P<filetype>csv|xls)$',
        data_views.resultado_parcial_categoria, name='resultado-parcial-categoria'
    ),
    url(
        r'^resultados-export/(?P<pk>\d+).(?P<filetype>csv|xls)$',
        views.ResultadosExport.as_view(), name='resultados-export'
    ),
    url(
        r'^resultados-en-base-a-configuración/(?P<pk>\d+)?$',
        views.ResultadosComputoCategoria.as_view(),        
        name='resultados-en-base-a-configuración'
    ),    
]
