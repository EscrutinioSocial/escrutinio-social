import itertools
from django.conf import settings
from functools import lru_cache
from collections import defaultdict, OrderedDict
from attrdict import AttrDict
from django.http import JsonResponse
from datetime import timedelta
from django.utils import timezone
from django.template.loader import render_to_string
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q, F, Sum, Count, Subquery
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.text import get_text_list
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from djgeojson.views import GeoJSONLayerView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseForbidden
from django.utils.functional import cached_property
from django.views import View
from django.contrib.auth.models import User
from fiscales.models import Fiscal
from django.db.models import Sum, IntegerField, Case, When
from .models import (
    Distrito,
    Seccion,
    Circuito,
    Categoria,
    Partido,
    Opcion,
    VotoMesaReportado,
    Carga,
    LugarVotacion,
    MesaCategoria,
    Mesa,
)
from .resultados import Resultados

ESTRUCTURA = {
    None: Seccion,
    Seccion: Circuito,
    Circuito: LugarVotacion,
    LugarVotacion: Mesa,
    Mesa: None
}

class StaffOnlyMixing:
    """
    Mixin para que sólo usuarios tipo "staff"
    accedan a la vista.
    """

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

class VisualizadoresOnlyMixin:
    """
    Mixin para que sólo usuarios visualizadores
    accedan a la vista.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.fiscal.esta_en_grupo('visualizadores'):
            return super().dispatch(request, *args, **kwargs)
        
        return HttpResponseForbidden()

class LugaresVotacionGeoJSON(GeoJSONLayerView):
    """
    Devuelve el archivo geojson con la información geoposicional
    de las escuelas, que es consumido por la el template de la
    vista :class:`Mapa`

    cada point tiene un color que determina si hay o no alguna mesa computada
    en esa escuela, ver  :attr:`elecciones.LugarVotacion.color`

    Documentación de referencia:

        https://django-geojson.readthedocs.io/
    """

    model = LugarVotacion
    properties = ('id', 'color')    # 'popup_html',)

    def get_queryset(self):
        qs = super().get_queryset()
        ids = self.request.GET.get('ids')
        if ids:
            qs = qs.filter(id__in=ids.split(','))
        elif 'todas' in self.request.GET:
            return qs
        elif 'testigo' in self.request.GET:
            qs = qs.filter(mesas__es_testigo=True).distinct()

        return qs


class EscuelaDetailView(StaffOnlyMixing, DetailView):
    """
    Devuelve una tabla estática con información general de una esuela
    que se muestra an un popup al hacer click sobre una escuela en :class:`Mapa`
    """
    template_name = "elecciones/detalle_escuela.html"
    model = LugarVotacion


class Mapa(StaffOnlyMixing, TemplateView):
    """
    Vista estática que carga el mapa que consume el geojson de escuelas
    el template utiliza leaflet

    https://django-leaflet.readthedocs.io/en/latest/

    """

    template_name = "elecciones/mapa.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        geojson_url = reverse("geojson")
        if 'ids' in self.request.GET:
            query = self.request.GET.urlencode()
            geojson_url += f'?{query}'
        elif 'testigo' in self.request.GET:
            query = 'testigo=si'
            geojson_url += f'?{query}'

        context['geojson_url'] = geojson_url
        return context


class ResultadosCategoria(VisualizadoresOnlyMixin, TemplateView):
    """
    Vista principal para el cálculo de resultados
    """

    template_name = "elecciones/resultados.html"

    def get(self, request, *args, **kwargs):
        for nivel in ['mesa', 'lugarvotacion', 'circuito', 'seccion', 'distrito']:
            if nivel in self.request.GET:
                kwargs['tipo'] = nivel
                kwargs['listado'] = self.request.GET.getlist(nivel)

        self.resultados = Resultados(kwargs, None) # Por ahora None
        return super().get(request, *args, **kwargs)

    def get_template_names(self):
        return [self.kwargs.get("template_name", self.template_name)]


    def status_filter(self, categoria, prefix='carga__mesa_categoria__'):
        return self.resultados.status_filter(categoria, prefix)

    @property
    def filtros(self):
        return self.resultados.filtros

    @lru_cache(128)
    def mesas(self, categoria):
        return self.resultados.mesas(categoria)

    @lru_cache(128)
    def electores(self, categoria):
        return self.resultados.electores(categoria)

    def get_resultados(self, categoria):
        proyectado = (
           self.request.method == "GET" and
           self.request.GET.get('tipodesumarizacion', '1') == str(2) and
           not self.filtros
        )

        resultados = self.resultados.get_resultados(categoria, proyectado)
        result_piechart = None
        if settings.SHOW_PLOT:
            result_piechart = [{
                'key': str(k),
                'y': v["votos"],
                'color': k.color if not isinstance(k, str) else '#CCCCCC'
            } for k, v in resultados['tabla_positivos'].items()]

        resultados['result_piechart'] = result_piechart
        return resultados

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipos_sumarizacion'] = Resultados.get_tipos_sumarizacion()
        context['tipo_sumarizacion_seleccionado'] = self.request.GET.get('tipodesumarizacion', '1')

        if self.filtros:
            context['para'] = get_text_list([objeto.nombre_completo() for objeto in self.filtros], " y ")
        else:
            context['para'] = 'el país'

        pk = self.kwargs.get('pk', 1)
        if pk == 1:
            pk == Categoria.objects.first().id
        categoria = get_object_or_404(Categoria, id=pk)
        context['object'] = categoria
        context['categoria_id'] = categoria.id
        context['resultados'] = self.get_resultados(categoria)
        context['show_plot'] = settings.SHOW_PLOT
        if settings.SHOW_PLOT:
            chart = context['resultados']['result_piechart']
            context['chart_values'] = [v['y'] for v in chart]
            context['chart_keys'] = [v['key'] for v in chart]
            context['chart_colors'] = [v['color'] for v in chart]

        # Las pestañas de categorías que se muestran son las que sean
        # comunes a todas las mesas filtradas.

        # Para el cálculo se filtran categorías activas que estén relacionadas
        # a las mesas.
        mesas = self.mesas(categoria)
        context['categorias'] = Categoria.para_mesas(mesas).order_by('id')

        context['distritos'] = Distrito.objects.all().order_by('numero')
        return context
