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

from django.http import HttpResponse
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
    Mesa,
)

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


class ResultadosCategoria(TemplateView):
    """
    Vista principal para el cálculo de resultados
    """

    template_name = "elecciones/resultados.html"

    def get_template_names(self):
        return [self.kwargs.get("template_name", self.template_name)]

    @classmethod
    def agregaciones_por_partido(cls, categoria):
        """
        Dada una categoria, devuelve los criterios de agregación
        aplicados a VotoMesaReporto para obtener una "tabla de resultados"
        que incluye agregaciones por partido politico (considerados positivos)
        y otros no positivos

        Se utilizan expresiones condicionales. Referencia

        https://docs.djangoproject.com/en/2.2/ref/models/conditional-expressions/
        """

        oficiales = True
        sum_por_partido = {}
        otras_opciones = {}

        for id in Partido.objects.filter(
            opciones__categorias__id=categoria.id
        ).distinct().values_list('id', flat=True):
            sum_por_partido[str(id)] = Sum(
                Case(
                    When(
                        opcion__partido__id=id,
                        carga__categoria=categoria,
                        then=F('votos')
                    ), output_field=IntegerField()
                )
            )

        for nombre, id in Opcion.objects.filter(
            categorias__id=categoria.id,
            partido__isnull=True,
            es_metadata=False
        ).values_list('nombre', 'id'):
            otras_opciones[nombre] = Sum(
                Case(
                    When(
                        opcion__id=id,
                        carga__categoria=categoria,
                        then=F('votos')
                    ), output_field=IntegerField()
                )
            )
        return sum_por_partido, otras_opciones

    @property
    def filtros(self):
        """
        A partir de los argumentos de urls, devuelve
        listas de seccion / circuito etc. para filtrar
        """
        if self.kwargs.get('tipo') == 'distrito':
            return Distrito.objects.filter(numero=self.kwargs.get('numero'))

        if self.kwargs.get('tipo') == 'seccion':
            return Seccion.objects.filter(numero=self.kwargs.get('numero'))

        if self.kwargs.get('tipo') == 'seccion':
            return Seccion.objects.filter(numero=self.kwargs.get('numero'))

        if self.kwargs.get('tipo') == 'circuito':
            return Circuito.objects.filter(numero=self.kwargs.get('numero'))

        if 'distrito' in self.request.GET:
            return Distrito.objects.filter(id__in=self.request.GET.getlist('distrito'))

        elif 'seccion' in self.request.GET:
            return Seccion.objects.filter(id__in=self.request.GET.getlist('seccion'))

        elif 'circuito' in self.request.GET:
            return Circuito.objects.filter(id__in=self.request.GET.getlist('circuito'))
        elif 'lugarvotacion' in self.request.GET:
            return LugarVotacion.objects.filter(id__in=self.request.GET.getlist('lugarvotacion'))
        elif 'mesa' in self.request.GET:
            return Mesa.objects.filter(id__in=self.request.GET.getlist('mesa'))

    @lru_cache(128)
    def mesas(self, categoria):
        """
        Considerando los filtros posibles, devuelve el conjunto de mesas
        asociadas a la categoria dada
        """
        lookups = Q()
        meta = {}
        if self.filtros:
            if self.filtros.model is Distrito:
                lookups = Q(lugar_votacion__circuito__seccion__distrito__in=self.filtros)

            if self.filtros.model is Seccion:
                lookups = Q(lugar_votacion__circuito__seccion__in=self.filtros)

            elif self.filtros.model is Circuito:
                lookups = Q(lugar_votacion__circuito__in=self.filtros)

            elif 'lugarvotacion' in self.request.GET:
                lookups = Q(lugar_votacion__id__in=self.filtros)

            elif 'mesa' in self.request.GET:
                lookups = Q(id__in=self.filtros)

        return Mesa.objects.filter(categoria=categoria).filter(lookups).distinct()

    @lru_cache(128)
    def electores(self, categoria):
        """
        devuelve el número de electores para :meth:`~.mesas`

        TODO: convertir esto en un método de ``MesaManager``
        """
        mesas = self.mesas(categoria)
        electores = mesas.aggregate(v=Sum('electores'))['v']
        return electores or 0

    def get_resultados(self, categoria):
        """
        realiza la contabilidad para la categoria, invocando al método
        ``calcular``.

        Si el se pasa el parámetro proyectado, se incluye un diccionario
        extra con la ponderación, invocando a ``calcular``para obtener los
        resultados parciales de cada subdistrito para luego realizar la ponderación
        """
        lookups = Q()
        lookups2 = Q()
        resultados = {}

        proyectado = 'proyectado' in self.request.GET and not self.filtros 

        if self.request.method == "GET" :
            proyectado = self.request.GET.get('tipodesumarizacion', '1') == str(2) and not self.filtros

        if self.filtros:
            if 'seccion' in self.request.GET:
                lookups = Q(mesa__lugar_votacion__circuito__seccion__in=self.filtros)
                lookups2 = Q(lugar_votacion__circuito__seccion__in=self.filtros)

            elif 'circuito' in self.request.GET:
                lookups = Q(mesa__lugar_votacion__circuito__in=self.filtros)
                lookups2 = Q(lugar_votacion__circuito__in=self.filtros)

            elif 'lugarvotacion' in self.request.GET:
                lookups = Q(mesa__lugar_votacion__in=self.filtros)
                lookups2 = Q(lugar_votacion__in=self.filtros)

            elif 'mesa' in self.request.GET:
                lookups = Q(mesa__id__in=self.filtros)
                lookups2 = Q(id__in=self.filtros)

        mesas = self.mesas(categoria)

        c = self.calcular(categoria, mesas)

        proyeccion_incompleta = []
        if proyectado:
            # La proyeccion se calcula sólo cuando no hay filtros (es decir, para provincia)
            # ponderando por secciones (o circuitos para secciones de "proyeccion ponderada")

            agrupaciones = list(itertools.chain(  # cast para reusar
                Circuito.objects.filter(seccion__proyeccion_ponderada=True),
                Seccion.objects.filter(proyeccion_ponderada=False)
            ))
            datos_ponderacion = {}

            electores_pond = 0
            for ag in agrupaciones:
                mesas = ag.mesas(categoria)
                datos_ponderacion[ag] = self.calcular(categoria, mesas)

                if not datos_ponderacion[ag]["escrutados"]:
                    proyeccion_incompleta.append(ag)
                else:
                    electores_pond += datos_ponderacion[ag]["electores"]
        expanded_result = {}
        for k, v in c.votos.items():
            porcentaje_total = f'{v*100/c.total:.2f}' if c.total else '-'
            porcentaje_positivos = f'{v*100/c.positivos:.2f}' if c.positivos and isinstance(k, Partido) else '-'
            expanded_result[k] = {
                "votos": v,
                "porcentajeTotal": porcentaje_total,
                "porcentajePositivos": porcentaje_positivos
            }
            if proyectado:
                acumulador_positivos = 0
                for ag in agrupaciones:
                    data = datos_ponderacion[ag]
                    if k in data["votos"] and data["positivos"]:
                        acumulador_positivos += data["electores"]*data["votos"][k]/data["positivos"]

                expanded_result[k]["proyeccion"] = f'{acumulador_positivos*100/electores_pond:.2f}'

        # TODO permitir opciones positivas no asociadas a partido.
        tabla_positivos = OrderedDict(
            sorted(
                [(k, v) for k, v in expanded_result.items() if isinstance(k, Partido)],
                key=lambda x: float(x[1]["proyeccion" if proyectado else "votos"]), reverse=True
            )
        )
        tabla_no_positivos = {k: v for k, v in c.votos.items() if not isinstance(k, Partido)}
        tabla_no_positivos["Positivos"] = c.positivos
        tabla_no_positivos = {
            k: {
                "votos": v,
                "porcentajeTotal": f'{v*100/c.total:.2f}' if c.total else '-'
            } for k, v in  tabla_no_positivos.items()
        }
        result_piechart = None
        if settings.SHOW_PLOT:
            result_piechart = [{
                'key': str(k),
                'y': v["votos"],
                'color': k.color if not isinstance(k, str) else '#CCCCCC'
            } for k, v in tabla_positivos.items()]
        resultados = {
            'tabla_positivos': tabla_positivos,
            'tabla_no_positivos': tabla_no_positivos,
            'result_piechart': result_piechart,

            'electores': c.electores,
            'positivos': c.positivos,
            'escrutados': c.escrutados,
            'votantes': c.total,

            'proyectado': proyectado,
            'proyeccion_incompleta': proyeccion_incompleta,
            'porcentaje_mesas_escrutadas': c.porcentaje_mesas_escrutadas,
            'porcentaje_escrutado': f'{c.escrutados*100/c.electores:.2f}' if c.electores else '-',
            'porcentaje_participacion': f'{c.total*100/c.escrutados:.2f}' if c.escrutados else '-',
            'total_mesas_escrutadas': c.total_mesas_escrutadas,
            'total_mesas': c.total_mesas
        }
        return resultados

    def calcular(self, categoria, mesas):
        """
        Implementa los cómputos escenciales de la categoria para las mesas dadas.
        Se invoca una vez para el cálculo de resultados y N veces para los proyectados.

        Devuelve

            electores: cantidad de electores en las mesas válidas en la categoria
            escrutados: cantidad de electores en las mesas que efectivamente fueron escrutadas   # TODO revisar!
            porcentaje_mesas_escrutadas:
            votos: diccionario con resultados de votos por partido y opcion (positivos y no positivos)
            total: total votos (positivos + no positivos)
            positivos: total votos positivos
        """
        electores = mesas.filter(categoria=categoria).aggregate(v=Sum('electores'))['v'] or 0
        sum_por_partido, otras_opciones = ResultadosCategoria.agregaciones_por_partido(categoria)

        # primero para partidos

        reportados = VotoMesaReportado.objects.filter(
            carga__categoria=categoria, carga__mesa__in=Subquery(mesas.values('id'))
        )
        mesas_escrutadas = mesas.filter(cargas__votomesareportado__isnull=False).distinct()
        escrutados = mesas_escrutadas.aggregate(v=Sum('electores'))['v']
        if escrutados is None:
            escrutados = 0

        total_mesas_escrutadas = mesas_escrutadas.count()
        total_mesas = mesas.count()
        if total_mesas == 0:
            total_mesas = 1
        porcentaje_mesas_escrutadas = f'{total_mesas_escrutadas*100/total_mesas:.2f}'

        result = reportados.aggregate(
            **sum_por_partido
        )

        result = {Partido.objects.get(id=k): v for k, v in result.items() if v is not None}
        # no positivos
        result_opc = reportados.aggregate(
           **otras_opciones
        )
        result_opc = {k: v for k, v in result_opc.items() if v is not None}

        # calculamos el total como la suma de todos los positivos y los
        # validos no positivos.
        positivos = sum(result.values())
        total = positivos + sum(v for k, v in result_opc.items() if Opcion.objects.filter(nombre=k, es_contable=False, es_metadata=False).exists())
        result.update(result_opc)

        return AttrDict({
            "electores": electores,
            "escrutados": escrutados,
            "porcentaje_mesas_escrutadas": porcentaje_mesas_escrutadas,
            "votos": result,
            "total": total,
            "positivos": positivos,
            "total_mesas_escrutadas": total_mesas_escrutadas,
            "total_mesas": total_mesas
        })

    def get_tipos_sumarizacion(self):
        """
        Esto deberia cambiarse cuando se realice el issue 17
        Por ahora va a ser hardcodeado
        """
        return [{'pk': '1', 'name': 'Normal'}, {'pk': '2', 'name': 'Proyectado'}]


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipos_sumarizacion'] = self.get_tipos_sumarizacion()
        context['tipo_sumarizacion_seleccionado'] = self.request.GET.get('tipodesumarizacion', '1')

        if self.filtros:
            context['para'] = get_text_list([getattr(o, 'nombre', o) for o in self.filtros], " y ")
        else:
            context['para'] = 'Córdoba'

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

        # las pestañas de categorias que se muestran son las que sean
        # comunes a todas las mesas filtradas

        # para el calculo se filtran categorias activas que esten relacionadas
        # a las mesas
        mesas = self.mesas(categoria)
        context['categorias'] = Categoria.para_mesas(mesas).order_by('id')

        context['distritos'] = Distrito.objects.all().order_by('numero')
        return context
