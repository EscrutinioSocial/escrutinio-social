from functools import lru_cache
from collections import defaultdict, OrderedDict
from django.http import JsonResponse
from datetime import timedelta
from django.utils import timezone
from django.template.loader import render_to_string
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q, F, Sum, Count
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
from .models import *
from .models import LugarVotacion, Circuito, AgrupacionPK


POSITIVOS = 'TOTAL DE VOTOS AGRUPACIONES POLÍTICAS'
TOTAL = 'Total General'

class StaffOnlyMixing:

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class LugaresVotacionGeoJSON(GeoJSONLayerView):
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
    template_name = "elecciones/detalle_escuela.html"
    model = LugarVotacion



class Mapa(StaffOnlyMixing, TemplateView):
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


class ResultadosEleccion(StaffOnlyMixing, TemplateView):
    template_name = "elecciones/resultados.html"

    def get_template_names(self):
        return [self.kwargs.get("template_name", self.template_name)]

    @classmethod
    def agregaciones_por_partido(cls, eleccion):
        oficiales = True
        sum_por_partido = {}
        otras_opciones = {}

        for id in Partido.objects.filter(opciones__elecciones__id=eleccion.id).distinct().values_list('id', flat=True):
            sum_por_partido[str(id)] = Sum(Case(When(opcion__partido__id=id, then=F('votos')),
                                                output_field=IntegerField()))

        for nombre, id in Opcion.objects.filter(elecciones__id=eleccion.id, partido__isnull=True).values_list('nombre', 'id'):
            otras_opciones[nombre] = Sum(Case(When(opcion__id=id, eleccion__id=eleccion.id, then=F('votos')),
                                              output_field=IntegerField()))
        return sum_por_partido, otras_opciones

    @property
    def filtros(self):
        """a partir de los argumentos de urls, devuelve
        listas de seccion / circuito etc. para filtrar """
        if self.kwargs.get('tipo') == 'seccion':
            return Seccion.objects.filter(numero=self.kwargs.get('numero'))

        if self.kwargs.get('tipo') == 'circuito':
            return Circuito.objects.filter(numero=self.kwargs.get('numero'))

        elif 'seccion' in self.request.GET:
            return Seccion.objects.filter(id__in=self.request.GET.getlist('seccion'))


        elif 'circuito' in self.request.GET:
            return Circuito.objects.filter(id__in=self.request.GET.getlist('circuito'))
        elif 'lugarvotacion' in self.request.GET:
            return LugarVotacion.objects.filter(id__in=self.request.GET.getlist('lugarvotacion'))
        elif 'mesa' in self.request.GET:
            return Mesa.objects.filter(id__in=self.request.GET.getlist('mesa'))
        elif 'agrupacionpk' in self.request.GET:
            return AgrupacionPK.objects.filter(id__in=self.request.GET.getlist('agrupacionpk'))

    @lru_cache(128)
    def mesas(self, eleccion):
        lookups = Q()
        meta = {}
        if self.filtros:
            if self.filtros.model is Seccion:
                lookups = Q(lugar_votacion__circuito__seccion__in=self.filtros)

            elif self.filtros.model is Circuito:
                lookups = Q(lugar_votacion__circuito__in=self.filtros)

            elif 'lugarvotacion' in self.request.GET:
                lookups = Q(lugar_votacion__id__in=self.filtros)

            elif 'mesa' in self.request.GET:
                lookups = Q(id__in=self.filtros)

            elif 'agrupacionpk' in self.request.GET:
                lookups = Q(lugar_votacion__circuito__seccion_de_ponderacion__in=self.filtros)

        return Mesa.objects.filter(eleccion=eleccion).filter(lookups).distinct()

    @lru_cache(128)
    def electores(self, eleccion):
        mesas = self.mesas(eleccion)
        electores = mesas.aggregate(v=Sum('electores'))['v']
        return electores or 0

    def resultado_agrupacion(self, eleccion, agrupacion, sum_por_partido, otras_opciones):
        mesas_agrupacion = Mesa.objects.filter(
            lugar_votacion__circuito__seccion_de_ponderacion=agrupacion
        )
        mesas_escrutadas = mesas_agrupacion.filter(votomesareportado__isnull=False).distinct()
        electores = mesas_agrupacion.aggregate(v=Sum('electores'))['v']
        escrutados = mesas_escrutadas.aggregate(v=Sum('electores'))['v']
        reportados = VotoMesaReportado.objects.filter(
            mesa__lugar_votacion__circuito__seccion_de_ponderacion=agrupacion
        )

        result = reportados.aggregate(
            **sum_por_partido
        )
        result = {Partido.objects.get(id=k): v for k, v in result.items() if v is not None}

        # no positivos
        result_opc = reportados.aggregate(
            **otras_opciones
        )
        result_opc = {k: v for k, v in result_opc.items() if v is not None}

        positivos = result_opc.get(POSITIVOS, 0)
        total = result_opc.pop(TOTAL, 0)

        if not positivos:
            # si no vienen datos positivos explicitos lo calculamos
            # y redifinimos el total como la suma de todos los positivos y los
            # validos no positivos.
            positivos = sum(result.values())
            total = positivos + sum(v for k, v in result_opc.items() if Opcion.objects.filter(nombre=k, es_contable=False).exists())
            result.update(result_opc)
        else:
            result['Otros partidos'] = positivos - sum(result.values())     # infiere los datos no cargados (no requeridos)
            result['Blancos, impugnados, etc'] = total - positivos

        datos_ponderacion = {
            "electores": electores,
            "escrutados": escrutados,
            "votos": result,
            "total": total,
            "positivos": positivos
        }
        return datos_ponderacion


    def get_resultados(self, eleccion):
        lookups = Q()
        lookups2 = Q()
        resultados = {}
        proyectado = 'proyectado' in self.request.GET and not self.filtros

        sum_por_partido, otras_opciones = ResultadosEleccion.agregaciones_por_partido(eleccion)

        if self.filtros:
            if 'agrupacionpk' in self.request.GET:
                lookups = Q(mesa__lugar_votacion__circuito__seccion_de_ponderacion__in=self.filtros)
                lookups2 = Q(lugar_votacion__circuito__seccion_de_ponderacion__in=self.filtros)

            elif 'seccion' in self.request.GET:
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

        electores = self.electores(eleccion)
        # primero para partidos

        reportados = VotoMesaReportado.objects.filter(
            Q(eleccion=eleccion) & lookups
        )

        todas_mesas_escrutadas = Mesa.objects.filter(votomesareportado__in=reportados).distinct()
        escrutados = todas_mesas_escrutadas.aggregate(v=Sum('electores'))['v']
        if escrutados is None:
            escrutados = 0

        mesas_escrutadas = todas_mesas_escrutadas.count()
        total_mesas = Mesa.objects.filter(lookups2, eleccion=eleccion).count()
        porcentaje_mesas_escrutadas = f'{mesas_escrutadas*100/total_mesas:.2f}'


        result = reportados.aggregate(
            **sum_por_partido
        )

        result = {Partido.objects.get(id=k): v for k, v in result.items() if v is not None}

        # no positivos
        result_opc = VotoMesaReportado.objects.filter(
            Q(eleccion=eleccion) & lookups
        ).aggregate(
            **otras_opciones
        )
        result_opc = {k: v for k, v in result_opc.items() if v is not None}

        positivos = result_opc.get(POSITIVOS, 0)
        total = result_opc.pop(TOTAL, 0)

        if not positivos:
            # si no vienen datos positivos explicitos lo calculamos
            # y redifinimos el total como la suma de todos los positivos y los
            # validos no positivos.
            positivos = sum(result.values())
            total = positivos + sum(v for k, v in result_opc.items() if Opcion.objects.filter(nombre=k, es_contable=False).exists())
            result.update(result_opc)
        else:
            result['Otros partidos'] = positivos - sum(result.values())
            result['Blancos, impugnados, etc'] = total - positivos

        if proyectado:
            # solo provincias
            agrupaciones = AgrupacionPK.objects.all().order_by("numero")
            datos_ponderacion = {}

            electores_pond = 0
            proyeccion_incompleta = []
            for ag in agrupaciones:
                datos_ponderacion[ag] = self.resultado_agrupacion(eleccion, ag, sum_por_partido, otras_opciones)
                if datos_ponderacion[ag]["escrutados"] is None:
                    proyeccion_incompleta.append(f"{ag}")
#                    proyeccion_incompleta.append(str(ag.numero)+"-"+ag.nombre)
                else:
                    electores_pond += datos_ponderacion[ag]["electores"]

            print(proyeccion_incompleta)

        expanded_result = {}
        for k, v in result.items():

            porcentaje_total = f'{v*100/total:.2f}' if total else '-'
            porcentaje_positivos = f'{v*100/positivos:.2f}' if positivos and isinstance(k, Partido) else '-'
            expanded_result[k] = {
                "votos": v,
                "porcentajeTotal": porcentaje_total,
                "porcentajePositivos": porcentaje_positivos
            }
            if proyectado:
                acumulador_total = 0
                acumulador_positivos = 0
                for ag in agrupaciones:
                    data = datos_ponderacion[ag]
                    if k in data["votos"]:
                        acumulador_total += data["electores"]*data["votos"][k]/data["total"]
                        acumulador_positivos += data["electores"]*data["votos"][k]/data["positivos"]

                expanded_result[k]["proyeccionTotal"] = f'{acumulador_total *100/electores_pond:.2f}'
                expanded_result[k]["proyeccion"] = f'{acumulador_positivos *100/electores_pond:.2f}'

        result = expanded_result

        # TODO revisar si opciones contables no asociadas a partido.
        tabla_positivos = OrderedDict(
            sorted(
                [(k, v) for k,v in result.items() if isinstance(k, Partido)],
                key=lambda x: float(x[1]["proyeccion" if proyectado else "votos"]), reverse=True)
            )

        # como se hace para que los "Positivos" estén primeros en la tabla???

        tabla_no_positivos = {k:v for k,v in result.items() if not isinstance(k, Partido)}
        tabla_no_positivos["Positivos"] = {
            "votos": positivos,
            "porcentajeTotal": f'{positivos*100/total:.2f}' if total else '-'
        }
        result_piechart = [
            {'key': str(k),
             'y': v["votos"],
             'color': k.color if not isinstance(k, str) else '#CCCCCC'} for k, v in tabla_positivos.items()
        ]
        resultados = {'tabla_positivos': tabla_positivos,
                      'tabla_no_positivos': tabla_no_positivos,
                      'result_piechart': result_piechart,
                      'electores': electores,
                      'positivos': positivos,
                      'escrutados': escrutados,
                      'votantes': total,
                      'proyectado': proyectado,
                      'porcentaje_mesas_escrutadas': porcentaje_mesas_escrutadas,
                      'porcentaje_escrutado': f'{escrutados*100/electores:.2f}' if electores else '-',
                      'porcentaje_participacion': f'{total*100/escrutados:.2f}' if escrutados else '-',
                    }
        if proyectado:
            resultados["proyeccion_incompleta"] = proyeccion_incompleta

        return resultados

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.filtros:
            context['para'] = get_text_list([o.nombre for o in self.filtros], " y ")
        else:
            context['para'] = 'Córdoba'
        eleccion = get_object_or_404(Eleccion, id=self.kwargs.get('pk', 1))
        context['object'] = eleccion
        context['eleccion_id'] = eleccion.id
        context['resultados'] = self.get_resultados(eleccion)
        chart = context['resultados']['result_piechart']

        context['chart_values'] = [v['y'] for v in chart]
        context['chart_keys'] = [v['key'] for v in chart]
        context['chart_colors'] = [v['color'] for v in chart]

        if not self.filtros:
            context['elecciones'] = [Eleccion.objects.first()]
        else:
            # solo las elecciones comunes a todas las mesas
            mesas = self.mesas(eleccion)
            elecciones = Eleccion.objects.filter(mesa__in=mesas).annotate(num_mesas=Count('mesa')).filter(num_mesas=mesas.count())
            context['elecciones'] = elecciones.order_by('id')

            # context['elecciones'] = reduce(lambda x, y: x & y, (m.eleccion.all() for m in self.mesas(eleccion)))

        context['secciones'] = Seccion.objects.all()
        context['agrupacionpk'] = AgrupacionPK.objects.all()

        return context



@user_passes_test(lambda u: u.is_superuser)
def dashboard(request):
    """
    un panel con stats utiles
    """

    desde = timezone.now() - timedelta(minutes=5)

    # usuarios que se acaban de loguear o han guardado un acta en los ultimos 5 minutos
    # TODO considerar los que sólo clasifican actas
    fiscales_online = Fiscal.objects.filter(Q(user__last_login__gte=desde) | Q(votomesareportado__created__gte=desde)).distinct()

    data = {'dataentries online': fiscales_online.count()}
    data['tiempo_de_carga'] = {str(f): f.tiempo_de_carga() for f in fiscales_online}

    data['tiempo_de_carga_promedio'] = sum(data['tiempo_de_carga'].values()) / data['dataentries online'] if data['dataentries online'] else '-'

    return JsonResponse(data)

