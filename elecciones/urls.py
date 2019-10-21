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
    url(r'^avance_carga_resumen/(?P<carga_parcial>\w+)/(?P<carga_total>\w+)/(?P<restriccion_geografica>(\w|-)+)/(?P<categoria>\w+)/(?P<data_extra>\w+)$',
        views.AvanceDeCargaResumen.as_view(), name='avance-carga-resumen'),
    url(r'^avance_carga_resumen_elegir_categoria/(?P<carga_parcial>\w+)/(?P<carga_total>\w+)/(?P<restriccion_geografica>(\w|-)+)/(?P<data_extra>\w+)$',
        views.elegir_categoria_avance_carga_resumen, name='avance-carga-resumen-elegir-categoria'),
    url(r'^avance_carga_resumen_elegir_detalle/(?P<carga_parcial>\w+)/(?P<carga_total>\w+)/(?P<restriccion_geografica>(\w|-)+)/(?P<categoria>\w+)/(?P<data_extra>\w+)/(?P<seleccion>\w+)$',
        views.elegir_detalle_avance_carga_resumen, name='avance-carga-resumen-elegir-detalle'),
    url(r'^elegir_distrito_o_seccion/(?P<hay_criterio>\w+)/(?P<valor_criterio>(\w|-|\s)*)/(?P<donde_volver>(\w|-)+)/(?P<mensaje>(\w|-)+)$',
        views.EleccionDeDistritoOSeccion.as_view(), name='elegir-distrito-o-seccion'),
    url(r'^ingresar_parametro_busqueda/(?P<donde_volver>(\w|-)+)$',
        views.ingresar_parametro_busqueda, name='ingresar-parametro-busqueda'),
    url(r'^limpiar_busqueda/(?P<donde_volver>(\w|-)+)$',
        views.limpiar_busqueda, name='limpiar-busqueda'),
    url(r'^eleccion_efectiva_distrito_o_seccion/(?P<donde_volver>(\w|-)+)$',
        views.eleccion_efectiva_distrito_o_seccion, name='eleccion-efectiva-distrito-o-seccion'),
    url(
        r'^resultados-nuevo-menu/(?P<categoria_id>\d+)?$',
        cache_page(60 * 60)(views.menu_lateral_resultados),
        name='resultados-nuevo-menu'
    ),
    url(
        r'^resultados/(?P<pk>\d+)?$',
        cache_page(0)(views.ResultadosCategoria.as_view()),
        name='resultados-categoria'
    ),
    url(
        r'^resultados-cuerpo-central/(?P<pk>\d+)?$',
        cache_page(5 * 60)(views.ResultadosCategoriaCuerpoCentral.as_view()),
        name='resultados-categoria-cuerpo-central'
    ),
    url(
        r'^resultados/mesas_circuito/(?P<pk>\d+)?$',
        cache_page(5 * 60)(views.MesasDeCircuito.as_view()),
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
        r'^resultados-en-base-a-configuracion/(?P<pk>\d+)?$',
        views.ResultadosComputoCategoria.as_view(),
        name='resultados-en-base-a-configuracion'
    ),
]
