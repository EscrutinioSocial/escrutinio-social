# -*- coding: utf-8 -*-
from django.conf.urls import url
from . import views
from fancy_cache import cache_page
from django.contrib.auth.decorators import login_required


cached = cache_page(300)


urlpatterns = [
    url('^escuelas.geojson$', cached(views.LugaresVotacionGeoJSON.as_view()), name='geojson'),
    url('^escuelas/(?P<pk>\d+)$', views.EscuelaDetailView.as_view(), name='detalle_escuela'),
    url('^mapa/$', login_required(cached(views.Mapa.as_view())), name='mapa'),

    url('^resultadospk/$', login_required(cached(views.ResultadosEleccion.as_view())), { "template_name" : "elecciones/resultadospk.html"}, name='resultados-pk-eleccion'),
    url('^resultados/$', login_required(cached(views.ResultadosEleccion.as_view())), name='resultados-eleccion'),

    # url(r'^fiscal_mesa/', views.fiscal_mesa, name='fiscal_mesa'),
]
