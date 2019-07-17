import itertools
from django.conf import settings
from functools import lru_cache
from collections import defaultdict, OrderedDict
from attrdict import AttrDict
from functools import lru_cache
from model_utils import Choices
from django.db.models import Q, F, Sum, Count, Subquery
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

def porcentaje(numerador, denominador):
    """
    Expresa la razón numerador/denominador como un string correspondiente
    al porcentaje con 2 dígitos decimales.
    Si no puede calcularse, devuelve '-'.
    """
    if denominador and denominador > 0:
        return f'{numerador*100/denominador:.2f}'
    return '-'

class Resultados():
    """
    Esta clase encapsula el cómputo de resultados.
    """
    TIPOS_DE_AGREGACIONES = Choices(
        'todas_las_cargas',
        'solo_consolidados',
        'solo_consolidados_doble_carga'
    )
    OPCIONES_A_CONSIDERAR = Choices(
        'prioritarias',
        'todas'
    )

    def __init__(self, kwargs, tipo_de_agregacion, opciones_a_considerar):
        """
        El tipo de cómputo indica qué datos se tienen en cuenta y cuáles no.
        """
        self.kwargs = kwargs
        self.tipo_de_agregacion = tipo_de_agregacion  # Es una de TIPOS_DE_AGREGACIONES
        # Es una de OPCIONES_A_CONSIDERAR
        self.opciones_a_considerar = opciones_a_considerar
        self.nivel_de_agregacion = kwargs.get(
            'nivel_de_agregacion')  # Era tipo

        # Los ids de la unidad correspondiente según el nivel de agregación
        # (si es Mesa, entonces son ids de mesas, y así)
        # Era listado.
        self.ids_a_considerar = self.kwargs.get('ids_a_considerar')
        # XXX Si viene un número transformarlo en id.

    @lru_cache(128)
    def cargas_a_considerar_status_filter(self, categoria, prefix='carga__mesa_categoria__'):
        """
        Esta función devuelve los filtros que indican qué cargas se consideran para hacer el
        cómputo.
        """
        lookups = dict()

        # ['status'] == 'tc':
        if self.tipo_de_agregacion == TIPOS_DE_AGREGACIONES.solo_consolidados_doble_carga:
            if self.opciones_a_considerar == OPCIONES_A_CONSIDERAR.todas:
                lookups[f'{prefix}status'] = MesaCategoria.STATUS.total_consolidada_dc
            else:  # éste era pc
                lookups[f'{prefix}status'] = MesaCategoria.STATUS.parcial_consolidada_dc

        elif self.tipo_de_agregacion == TIPOS_DE_AGREGACIONES.solo_consolidados:  # no estaba
            # Doble carga y CSV.
            if self.opciones_a_considerar == OPCIONES_A_CONSIDERAR.todas:
                lookups[f'{prefix}status__in'] = (
                    MesaCategoria.STATUS.total_consolidada_dc,
                    MesaCategoria.STATUS.total_consolidada_csv,
                )
            else:
                lookups[f'{prefix}status__in'] = (
                    MesaCategoria.STATUS.parcial_consolidada_dc,
                    MesaCategoria.STATUS.parcial_consolidada_csv,
                )

        # ['status'] == 'tsc':
        elif self.tipo_de_agregacion == TIPOS_DE_AGREGACIONES.todas_las_cargas:
            if self.opciones_a_considerar == OPCIONES_A_CONSIDERAR.todas:
                lookups[f'{prefix}status__in'] = (
                    MesaCategoria.STATUS.total_consolidada_dc,
                    MesaCategoria.STATUS.total_consolidada_csv,
                    MesaCategoria.STATUS.total_sin_consolidar,
                )
            else:  # este era psc
                lookups[f'{prefix}status__in'] = (
                    MesaCategoria.STATUS.parcial_consolidada_dc,
                    MesaCategoria.STATUS.parcial_consolidada_csv,
                    MesaCategoria.STATUS.parcial_sin_consolidar,
                )

        return lookups

    def agregaciones_por_partido(self, categoria):  # XXX Cambiar nombre.
        """
        Dada una categoría, devuelve los criterios de agregación
        aplicados a VotoMesaReportado para obtener una "tabla de resultados"
        que incluye agregaciones por partido político (considerados positivos)
        y otros no positivos.

        Se utilizan expresiones condicionales. Referencia

        https://docs.djangoproject.com/en/2.2/ref/models/conditional-expressions/
        """
        sum_por_partido = {}
        sum_por_opcion_no_partidaria = {}
        cargas_a_considerar_status_filter = self.cargas_a_considerar_status_filter(
            categoria)

        ids_partidos = Partido.objects.filter(
            opciones__categorias__id=categoria.id
        ).distinct().values_list('id', flat=True)
        for id in ids_partidos:
            sum_por_partido[str(id)] = Sum(
                Case(
                    When(
                        opcion__partido__id=id,
                        carga__mesa_categoria__categoria=categoria,
                        carga__es_testigo__isnull=False,
                        then=F('votos'),
                        **cargas_a_considerar_status_filter

                    ), output_field=IntegerField()
                )
            )

        ids_opciones_no_partidarias = Opcion.objects.filter(
            categorias__id=categoria.id,
            partido__isnull=True,
            es_metadata=False
        ).values_list('nombre', 'id')
        for nombre, id in ids_opciones_no_partidarias:
            sum_por_opcion_no_partidaria[nombre] = Sum(
                Case(
                    When(
                        opcion__id=id,
                        carga__mesa_categoria__categoria=categoria,
                        carga__es_testigo__isnull=False,
                        then=F('votos'),
                        **cargas_a_considerar_status_filter
                    ), output_field=IntegerField()
                )
            )
        return sum_por_partido, sum_por_opcion_no_partidaria

    @property
    def filtros(self):
        """
        Devuelve listas de sección, circuito, etc. para filtrar.
        """
        if not self.ids_a_considerar:
            return

        if self.nivel_de_agregacion == Eleccion.NIVELES_AGREGACION.distrito:
            return Distrito.objects.filter(id__in=self.ids_a_considerar)

        elif self.nivel_de_agregacion == Eleccion.NIVELES_AGREGACION.seccion:
            return Seccion.objects.filter(id__in=self.ids_a_considerar)

        elif self.nivel_de_agregacion == Eleccion.NIVELES_AGREGACION.circuito:
            return Circuito.objects.filter(id__in=self.ids_a_considerar)

        elif self.nivel_de_agregacion == Eleccion.NIVELES_AGREGACION.lugar_de_votacion:
            return LugarVotacion.objects.filter(id__in=self.ids_a_considerar)

        elif self.nivel_de_agregacion == Eleccion.NIVELES_AGREGACION.mesa:
            return Mesa.objects.filter(id__in=self.ids_a_considerar)

    @lru_cache(128)
    def mesas(self, categoria):
        """
        Considerando los filtros posibles, devuelve el conjunto de mesas
        asociadas a la categoría dada.
        """
        lookups = Q()
        meta = {}
        if self.filtros:
            if self.filtros.model is Distrito:
                lookups = Q(
                    lugar_votacion__circuito__seccion__distrito__in=self.filtros)

            if self.filtros.model is Seccion:
                lookups = Q(lugar_votacion__circuito__seccion__in=self.filtros)

            elif self.filtros.model is Circuito:
                lookups = Q(lugar_votacion__circuito__in=self.filtros)

            elif self.filtros.model is LugarVotacion:
                lookups = Q(lugar_votacion__id__in=self.filtros)

            elif self.filtros.model is Mesa:
                lookups = Q(id__in=self.filtros)

        return Mesa.objects.filter(categorias=categoria).filter(lookups).distinct()

    @lru_cache(128)
    def electores(self, categoria):
        """
        Devuelve el número de electores para :meth:`~.mesas`

        TODO: convertir esto en un método de ``MesaManager``
        """
        mesas = self.mesas(categoria)
        electores = mesas.aggregate(v=Sum('electores'))['v']
        return electores or 0

    def get_resultados(self, categoria):
        """
        Realiza la contabilidad para la categoría, invocando al método
        ``calcular``.
        """
        resultados = {}

        mesas = self.mesas(categoria)

        c = self.calcular(categoria, mesas)

        expanded_result = {}
        for k, v in c.votos.items():
            porcentaje_total = f'{v*100/c.total:.2f}' if c.total else '-'
            porcentaje_positivos = f'{v*100/c.positivos:.2f}' if c.total_positivos and isinstance(k, Partido) else '-'
            expanded_result[k] = {
                "votos": v,
                "porcentajeTotal": porcentaje_total,
                "porcentajePositivos": porcentaje_positivos
            }

        # TODO permitir opciones positivas no asociadas a partido.
        tabla_positivos = OrderedDict(
            sorted(
                [(k, v) for k, v in expanded_result.items()
                 if isinstance(k, Partido)],
                key=lambda x: float(x[1]["votos"]), reverse=True
            )
        )
        tabla_no_positivos = {
            k: v for k, v in c.votos.items() if not isinstance(k, Partido)}
        tabla_no_positivos["Positivos"] = c.positivos
        tabla_no_positivos = {
            k: {
                "votos": v,
                "porcentajeTotal": f'{v*100/c.total:.2f}' if c.total else '-'
            } for k, v in tabla_no_positivos.items()
        }

        resultados = {
            'tabla_positivos': tabla_positivos,
            'tabla_no_positivos': tabla_no_positivos,

            'electores': c.electores,
            'positivos': c.positivos,
            'electores_en_mesas_escrutadas': c.electores_en_mesas_escrutadas,
            'votantes': c.total,

            'proyectado': proyectado,
            'proyeccion_incompleta': proyeccion_incompleta,
            'porcentaje_mesas_escrutadas': c.porcentaje_mesas_escrutadas,
            'porcentaje_escrutado': f'{c.electores_en_mesas_escrutadas*100/c.electores:.2f}' if c.electores else '-',
            'porcentaje_participacion': f'{c.total*100/c.electores_en_mesas_escrutadas:.2f}' if c.electores_en_mesas_escrutadas else '-',
            'total_mesas_escrutadas': c.total_mesas_escrutadas,
            'total_mesas': c.total_mesas
        }
        return resultados

    def calcular(self, categoria, mesas):
        """
        Implementa los cómputos esenciales de la categoría para las mesas dadas.
        Se invoca una vez para el cálculo de resultados y N veces para los proyectados.

        Devuelve

            electores: cantidad de electores en las mesas válidas de la categoría
            electores_en_mesas_escrutadas: cantidad de electores en las mesas que efectivamente fueron escrutadas
            porcentaje_mesas_escrutadas:
            votos: diccionario con resultados de votos por partido y opción (positivos y no positivos)
            total_positivos: total votos positivos
            total: total votos (positivos + no positivos)
        """

        # 1) Mesas.

        # Me quedo con las mesas que corresponden de acuerdo a los parámetros
        # y la categoría, que tengan la carga testigo para esa categoría.
        mesas_escrutadas = mesas.filter(
            mesacategoria__categoria=categoria,
            mesacategoria__carga_testigo__isnull=False,
            **self.cargas_a_considerar_status_filter(categoria, 'mesacategoria__')
        ).distinct()

        total_mesas_escrutadas = mesas_escrutadas.count()
        total_mesas = mesas.count()

        porcentaje_mesas_escrutadas = porcentaje(total_mesas_escrutadas, total_mesas)

        # 2) Electores.

        electores = mesas.filter(categorias=categoria).aggregate(
            v=Sum('electores'))['v'] or 0
        electores_en_mesas_escrutadas = mesas_escrutadas.aggregate(v=Sum('electores'))[
            'v'] or 0

        # 3) Votos 

        sum_por_partido, sum_por_opcion_no_partidaria = self.agregaciones_por_partido(
            categoria)

        # Me quedo con los votos reportados pertenecientes a las "cargas testigo"
        # de las mesas que corresponden de acuerdo a los parámetros y la categoría.
        votos_reportados = VotoMesaReportado.objects.filter(
            carga__mesa_categoria__mesa__in=Subquery(mesas.values('id')),
            carga__es_testigo__isnull=False,
            **self.cargas_a_considerar_status_filter(categoria)
        )

        # 3.1) Partidos. XXX Esto no entiendo qué hace.
        votos_por_opcion = votos_reportados.aggregate(
            **sum_por_partido
        )

        votos_por_opcion = {Partido.objects.get(
            id=k): v for k, v in votos_por_opcion.items() if v is not None}

        # 3.2) Opciones no partidarias.
        result_opc = reportados.aggregate(
            **sum_por_opcion_no_partidaria
        )
        result_opc = {k: v for k, v in result_opc.items() if v is not None}

        # Calculamos el total como la suma de todos los positivos y los
        # válidos no positivos.
        total_positivos = sum(result.values())
        total = positivos + sum(v for k, v in result_opc.items() if Opcion.objects.filter(
            nombre=k, es_contable=False, es_metadata=False).exists())
        votos_por_opcion.update(result_opc)

        return AttrDict({
            "total_mesas": total_mesas
            "total_mesas_escrutadas": total_mesas_escrutadas,
            "porcentaje_mesas_escrutadas": porcentaje_mesas_escrutadas,

            "electores": electores,
            "electores_en_mesas_escrutadas": electores_en_mesas_escrutadas,

            "votos": votos_por_opcion,
            "total_positivos": total_positivos,
            "total": total,
        })

    @classmethod
    def get_tipos_sumarizacion(cls):
        id = 0
        tipos_sumarizacion = []
        for tipo_de_agregacion in TIPOS_DE_AGREGACIONES:
            for opcion in OPCIONES_A_CONSIDERAR:
                tipos_sumarizacion.append('pk': str(id), 'name': tipo_de_agregacion + '-' + opcion)

        return tipos_sumarizacion


class Proyecciones(Resultados):
    """
    Esta clase encapsula el cómputo de proyecciones.
    """

    def get_resultados(self, categoria):
        """
        Realiza la contabilidad para la categoría, invocando al método
        ``calcular``.

        Si se le pasa el parámetro `proyectado`, se incluye un diccionario
        extra con la ponderación, invocando a ``calcular`` para obtener los
        resultados parciales de cada subdistrito para luego realizar la ponderación.
        """
        lookups = Q()
        lookups2 = Q()
        resultados = {}
        proyectado = True

        if self.filtros:
            if self.nivel_de_agregacion == 'seccion':
                lookups = Q(
                    mesa__lugar_votacion__circuito__seccion__in=self.filtros)
                lookups2 = Q(
                    lugar_votacion__circuito__seccion__in=self.filtros)

            elif self.nivel_de_agregacion == 'circuito':
                lookups = Q(mesa__lugar_votacion__circuito__in=self.filtros)
                lookups2 = Q(lugar_votacion__circuito__in=self.filtros)

            elif self.nivel_de_agregacion == 'lugarvotacion':
                lookups = Q(mesa__lugar_votacion__in=self.filtros)
                lookups2 = Q(lugar_votacion__in=self.filtros)

            elif self.nivel_de_agregacion == Eleccion.NIVELES_AGREGACION.mesa:
                lookups = Q(mesa__id__in=self.filtros)
                lookups2 = Q(id__in=self.filtros)

        mesas = self.mesas(categoria)

        c = self.calcular(categoria, mesas)

        proyeccion_incompleta = []
        if proyectado:
            # La proyección se calcula sólo cuando no hay filtros (es decir, para todo el universo)
            # ponderando por secciones (o circuitos para secciones de "proyeccion ponderada").

            agrupaciones = list(itertools.chain(  # cast para reusar
                Circuito.objects.filter(seccion__proyeccion_ponderada=True),
                Seccion.objects.filter(proyeccion_ponderada=False)
            ))
            datos_ponderacion = {}

            electores_pond = 0
            for ag in agrupaciones:
                mesas = ag.mesas(categoria)
                datos_ponderacion[ag] = self.calcular(categoria, mesas)

                if not datos_ponderacion[ag]["electores_en_mesas_escrutadas"]:
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
                    if k in data["votos"] and data["total_positivos"]:
                        acumulador_positivos += data["electores"] * \
                            data["votos"][k] / data["positivos"]

                expanded_result[k]["proyeccion"] = f'{acumulador_positivos*100/electores_pond:.2f}'

        # TODO permitir opciones positivas no asociadas a partido.
        tabla_positivos = OrderedDict(
            sorted(
                [(k, v) for k, v in expanded_result.items()
                 if isinstance(k, Partido)],
                key=lambda x: float(x[1]["proyeccion" if proyectado else "votos"]), reverse=True
            )
        )
        tabla_no_positivos = {
            k: v for k, v in c.votos.items() if not isinstance(k, Partido)}
        tabla_no_positivos["Positivos"] = c.positivos
        tabla_no_positivos = {
            k: {
                "votos": v,
                "porcentajeTotal": f'{v*100/c.total:.2f}' if c.total else '-'
            } for k, v in tabla_no_positivos.items()
        }
        result_piechart = None

        resultados = {
            'tabla_positivos': tabla_positivos,
            'tabla_no_positivos': tabla_no_positivos,
            'result_piechart': result_piechart,

            'electores': c.electores,
            'total_positivos': c.total_positivos,
            'electores_en_mesas_escrutadas': c.electores_en_mesas_escrutadas,
            'votantes': c.total,

            'proyectado': proyectado,
            'proyeccion_incompleta': proyeccion_incompleta,
            'porcentaje_mesas_escrutadas': c.porcentaje_mesas_escrutadas,
            'porcentaje_escrutado': f'{c.electores_en_mesas_escrutadas*100/c.electores:.2f}' if c.electores else '-',
            'porcentaje_participacion': f'{c.total*100/c.electores_en_mesas_escrutadas:.2f}' if c.electores_en_mesas_escrutadas else '-',
            'total_mesas_escrutadas': c.total_mesas_escrutadas,
            'total_mesas': c.total_mesas
        }
        return resultados
