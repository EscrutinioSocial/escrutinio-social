"""
Vistas con datos crudos
"""

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


class RawDataView(TemplateView):
    
    def agregaciones_por_partido(self, eleccion):
        
        sum_por_partido = {}
        otras_opciones = {}

        partidos_ids = Partido.objects.filter(opciones__elecciones__id=eleccion.id).distinct().values_list('id', flat=True)
        for partido_id in partidos_ids:
            sum_por_partido[str(partido_id)] = Sum(Case(When(opcion__partido__id=partido_id, eleccion=eleccion, then=F('votos')),
                                                output_field=IntegerField()))

        opciones_ids = Opcion.objects.filter(elecciones__id=eleccion.id, partido__isnull=True).values_list('nombre', 'id')
        for nombre, opcion_id in opciones_ids:
            otras_opciones[nombre] = Sum(Case(When(opcion__id=opcion_id, eleccion=eleccion, then=F('votos')),
                                              output_field=IntegerField()))
        return sum_por_partido, otras_opciones

    @lru_cache(128)
    def electores(self, eleccion):
        mesas = Mesa.objects.filter(eleccion=eleccion)
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

        result = reportados.aggregate(**sum_por_partido)
        result = {Partido.objects.get(id=k): v for k, v in result.items() if v is not None}

        # no positivos
        result_opc = reportados.aggregate(**otras_opciones)
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


    def get_resultados(self, eleccion, proyectado=False):
        resultados = {}
        
        sum_por_partido, otras_opciones = self.agregaciones_por_partido(eleccion)

        electores = self.electores(eleccion)
        # primero para partidos

        reportados = VotoMesaReportado.objects.filter(Q(eleccion=eleccion))

        todas_mesas_escrutadas = Mesa.objects.filter(votomesareportado__in=reportados).distinct()
        escrutados = todas_mesas_escrutadas.aggregate(v=Sum('electores'))['v']
        if escrutados is None:
            escrutados = 0

        mesas_escrutadas = todas_mesas_escrutadas.count()
        total_mesas = Mesa.objects.filter(eleccion=eleccion).count()
        if total_mesas == 0:
            total_mesas = 1
        porcentaje_mesas_escrutadas = f'{mesas_escrutadas*100/total_mesas:.2f}'

        result = reportados.aggregate(**sum_por_partido)

        result = {Partido.objects.get(id=k): v for k, v in result.items() if v is not None}

        # no positivos
        result_opc = VotoMesaReportado.objects.filter(Q(eleccion=eleccion)).aggregate(**otras_opciones)
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