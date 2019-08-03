from django.conf import settings
from functools import lru_cache
from collections import OrderedDict
from attrdict import AttrDict
from model_utils import Choices
from django.db.models import Q, F, Sum, Subquery, IntegerField, OuterRef, Count
from .models import (
    Eleccion,
    Distrito,
    SeccionPolitica,
    Seccion,
    Circuito,
    Opcion,
    VotoMesaReportado,
    LugarVotacion,
    MesaCategoria,
    Mesa,
    TecnicaProyeccion,
    AgrupacionCircuitos,
    AgrupacionCircuito,
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


class Sumarizador():
    """
    Esta clase encapsula el cómputo de resultados.
    """
    TIPOS_DE_AGREGACIONES = Choices('todas_las_cargas', 'solo_consolidados', 'solo_consolidados_doble_carga')
    OPCIONES_A_CONSIDERAR = Choices('prioritarias', 'todas')

    def __init__(
        self,
        tipo_de_agregacion=TIPOS_DE_AGREGACIONES.todas_las_cargas,
        opciones_a_considerar=OPCIONES_A_CONSIDERAR.todas,
        nivel_de_agregacion=None,
        ids_a_considerar=None
    ):
        """
        El tipo de cómputo indica qué datos se tienen en cuenta y cuáles no.
        Las opciones a considerar, lo que su nombre indica (si sólo las prioritarias o todas).
        El nivel_de_agregacion indica qué se va a tener en cuenta: si es None es todo el país.
        Si no, toma opciones en Eleccion.NIVELES_AGREGACION (distrito, sección, etc.)
        Por último, los ids_a_considerar son los ids de unidades de el nivel `nivel_de_agregacion`
        que deben considerarse. Si es None se consideran todos.
        """
        self.tipo_de_agregacion = tipo_de_agregacion  # Es una de TIPOS_DE_AGREGACIONES
        # Es una de OPCIONES_A_CONSIDERAR
        self.opciones_a_considerar = opciones_a_considerar
        self.nivel_de_agregacion = nivel_de_agregacion

        self.ids_a_considerar = ids_a_considerar

    @lru_cache(128)
    def cargas_a_considerar_status_filter(self, categoria, prefix='carga__mesa_categoria__'):
        """
        Esta función devuelve los filtros que indican qué cargas se consideran para hacer el
        cómputo.
        """
        lookups = dict()

        if self.tipo_de_agregacion == self.TIPOS_DE_AGREGACIONES.solo_consolidados_doble_carga:
            if self.opciones_a_considerar == self.OPCIONES_A_CONSIDERAR.todas:
                lookups[f'{prefix}status'] = MesaCategoria.STATUS.total_consolidada_dc
            else:
                lookups[f'{prefix}status'] = MesaCategoria.STATUS.parcial_consolidada_dc

        elif self.tipo_de_agregacion == self.TIPOS_DE_AGREGACIONES.solo_consolidados:
            # Doble carga y CSV.
            if self.opciones_a_considerar == self.OPCIONES_A_CONSIDERAR.todas:
                lookups[f'{prefix}status__in'] = (
                    MesaCategoria.STATUS.total_consolidada_dc,
                    MesaCategoria.STATUS.total_consolidada_csv,
                )
            else:
                lookups[f'{prefix}status__in'] = (
                    MesaCategoria.STATUS.parcial_consolidada_dc,
                    MesaCategoria.STATUS.parcial_consolidada_csv,
                )

        elif self.tipo_de_agregacion == self.TIPOS_DE_AGREGACIONES.todas_las_cargas:
            if self.opciones_a_considerar == self.OPCIONES_A_CONSIDERAR.todas:
                lookups[f'{prefix}status__in'] = (
                    MesaCategoria.STATUS.total_consolidada_dc,
                    MesaCategoria.STATUS.total_consolidada_csv,
                    MesaCategoria.STATUS.total_sin_consolidar,
                )
            else:
                lookups[f'{prefix}status__in'] = (
                    MesaCategoria.STATUS.parcial_consolidada_dc,
                    MesaCategoria.STATUS.parcial_consolidada_csv,
                    MesaCategoria.STATUS.parcial_sin_consolidar,
                )

        return lookups

    @property
    def filtros(self):
        """
        Devuelve listas de sección, circuito, etc. para filtrar.
        """
        if not self.ids_a_considerar:
            return

        if self.nivel_de_agregacion == Eleccion.NIVELES_AGREGACION.distrito:
            return Distrito.objects.filter(id__in=self.ids_a_considerar)

        elif self.nivel_de_agregacion == Eleccion.NIVELES_AGREGACION.seccion_politica:
            return SeccionPolitica.objects.filter(id__in=self.ids_a_considerar)

        elif self.nivel_de_agregacion == Eleccion.NIVELES_AGREGACION.seccion:
            return Seccion.objects.filter(id__in=self.ids_a_considerar)

        elif self.nivel_de_agregacion == Eleccion.NIVELES_AGREGACION.circuito:
            return Circuito.objects.filter(id__in=self.ids_a_considerar)

        elif self.nivel_de_agregacion == Eleccion.NIVELES_AGREGACION.lugar_de_votacion:
            return LugarVotacion.objects.filter(id__in=self.ids_a_considerar)

        elif self.nivel_de_agregacion == Eleccion.NIVELES_AGREGACION.mesa:
            return Mesa.objects.filter(id__in=self.ids_a_considerar)

    def lookups_de_mesas(self):
        lookups = Q()
        if self.filtros:
            if self.filtros.model is Distrito:
                lookups = Q(lugar_votacion__circuito__seccion__distrito__in=self.filtros)

            if self.filtros.model is SeccionPolitica:
                lookups = Q(lugar_votacion__circuito__seccion__seccion_politica__in=self.filtros)

            elif self.filtros.model is Seccion:
                lookups = Q(lugar_votacion__circuito__seccion__in=self.filtros)

            elif self.filtros.model is Circuito:
                lookups = Q(lugar_votacion__circuito__in=self.filtros)

            elif self.filtros.model is LugarVotacion:
                lookups = Q(lugar_votacion__id__in=self.filtros)

            elif self.filtros.model is Mesa:
                lookups = Q(id__in=self.filtros)
        return lookups

    @lru_cache(128)
    def mesas(self, categoria):
        """
        Considerando los filtros posibles, devuelve el conjunto de mesas
        asociadas a la categoría dada.
        """
        lookups = self.lookups_de_mesas()
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

    def votos_reportados(self, categoria, mesas):
        """
        Me quedo con los votos reportados pertenecientes a las "cargas testigo"
        de las mesas que corresponden de acuerdo a los parámetros y la categoría.
        """
        return VotoMesaReportado.objects.filter(
            carga__mesa_categoria__mesa__in=Subquery(mesas.values('id')),
            carga__es_testigo__isnull=False,
            **self.cargas_a_considerar_status_filter(categoria)
        )

    def votos_por_opcion(self, categoria, mesas):
        """
        Dada una categoría y un conjunto de mesas, devuelve una tabla de resultados con la cantidad de
        votos por cada una de las opciones posibles (partidarias o no)
        """

        # Obtener los votos reportados
        votos_reportados = self.votos_reportados(categoria, mesas).values_list('opcion__id').annotate(
            sum_votos=Sum('votos')
        )

        # Diccionario inicial, opciones completas, todas en 0 (por si alguna opción no viene reportada).
        votos_por_opcion = {opcion.id: 0 for opcion in Opcion.objects.filter(categorias__id=categoria.id)}

        # Sobreescribir los valores default (en 0) con los votos reportados
        votos_por_opcion.update(votos_reportados)
        
        return votos_por_opcion.items()

    def agrupar_votos(self, votos_por_opcion):
        votos_positivos = {}
        votos_no_positivos = {}
        for id_opcion, sum_votos in votos_por_opcion:
            opcion = Opcion.objects.get(id=id_opcion)
            if opcion.partido:
                # 3.1 Opciones partidarias se agrupan con otras opciones del mismo partido.
                votos_positivos.setdefault(opcion.partido, {})[opcion] = sum_votos
            else:
                # 3.2 Opciones no partidarias
                # TODO ¿Puede realmente pasar que no vengan las opciones completas?
                votos_no_positivos[opcion.nombre] = sum_votos if sum_votos else 0

        return votos_positivos, votos_no_positivos

    def calcular(self, categoria, mesas):
        """
        Implementa los cómputos esenciales de la categoría para las mesas dadas.
        Se invoca una vez para el cálculo de resultados y N veces para los proyectados.

        Devuelve
            electores: cantidad de electores en las mesas válidas de la categoría
            electores_en_mesas_escrutadas: cantidad de electores en las mesas efectivamente escrutadas
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

        electores = mesas.filter(categorias=categoria).aggregate(v=Sum('electores'))['v'] or 0
        electores_en_mesas_escrutadas = mesas_escrutadas.aggregate(v=Sum('electores'))['v'] or 0

        # 3) Votos
        votos_por_opcion = self.votos_por_opcion(categoria, mesas)
        votos_positivos, votos_no_positivos = self.agrupar_votos(votos_por_opcion)

        return AttrDict({
            "total_mesas": total_mesas,
            "total_mesas_escrutadas": total_mesas_escrutadas,
            "porcentaje_mesas_escrutadas": porcentaje_mesas_escrutadas,
            "electores": electores,
            "electores_en_mesas_escrutadas": electores_en_mesas_escrutadas,
            "votos_positivos": votos_positivos,
            "votos_no_positivos": votos_no_positivos,
        })

    def get_resultados(self, categoria):
        """
        Realiza la contabilidad para la categoría, invocando al método
        ``calcular``.
        """
        self.categoria = categoria
        self.mesas_a_considerar = self.mesas(categoria)
        return Resultados(self.opciones_a_considerar, self.calcular(categoria, self.mesas_a_considerar))


class Resultados():
    """
    Esta clase contiene los resultados.
    """

    def __init__(self, opciones_a_considerar, resultados):
        self.opciones_a_considerar = opciones_a_considerar
        self.resultados = resultados

    @lru_cache(128)
    def total_positivos(self):
        """
        Devuelve el total de votos positivos, sumando los votos de cada una de las opciones de cada partido
        en el caso self.opciones_a_considerar == OPCIONES_A_CONSIDERAR.todas.

        En el caso self.self.opciones_a_considerar == OPCIONES_A_CONSIDERAR.prioritarias
        obtiene la opción de total
        """
        if self.opciones_a_considerar == Sumarizador.OPCIONES_A_CONSIDERAR.todas:
            total_positivos = sum(
                sum(votos for votos in opciones_partido.values() if votos)
                for opciones_partido in self.resultados.votos_positivos.values()
            )
        else:
            nombre_opcion_total = settings.OPCION_TOTAL_VOTOS['nombre']
            total = self.resultados.votos_no_positivos[nombre_opcion_total]
            total_no_positivos = self.total_no_positivos()
            total_positivos = total - total_no_positivos

        return total_positivos

    @lru_cache(128)
    def total_no_positivos(self):
        """
        Devuelve el total de votos no positivos, sumando los votos a cada opción no partidaria
        y excluyendo la opción que corresponde a totales (como el total de votantes o de sobres).
        """
        nombre_opcion_total = settings.OPCION_TOTAL_VOTOS['nombre']
        nombre_opcion_sobres = settings.OPCION_TOTAL_SOBRES['nombre']
        return sum(
            votos for opcion, votos in self.resultados.votos_no_positivos.items()
            if opcion not in (nombre_opcion_total, opcion != nombre_opcion_sobres)
        )

    @lru_cache(128)
    def votantes(self):
        """
        Total de personas que votaron.
        """
        return self.total_positivos() + self.total_no_positivos()

    @lru_cache(128)
    def tabla_positivos(self):
        """
        Devuelve toda la información sobre los votos positivos para mostrar.
        Para cada partido incluye:
            - votos: total de votos del partido
            - detalle: los votos de cada opción dentro del partido (recordar que es una PASO).
                Para cada opción incluye:
                    - votos: cantidad de votos para esta opción.
                    - porcentaje: porcentaje sobre el total del del partido.
                    - porcentaje_positivos: porcentaje sobre el total de votos positivos.
                    - porcentaje_total: porcentaje sobre el total de votos.
        """
        votos_positivos = {}
        for partido, votos_por_opcion in self.resultados.votos_positivos.items():
            total_partido = sum(filter(None, votos_por_opcion.values()))
            votos_positivos[partido] = {
                'votos': total_partido,
                'porcentaje_positivos': porcentaje(total_partido, self.total_positivos()),
                'porcentaje_total': porcentaje(total_partido, self.votantes()),
                'detalle': {
                    opcion: {
                        'votos': votos_opcion,
                        'porcentaje': porcentaje(votos_opcion, total_partido),
                        'porcentaje_positivos': porcentaje(votos_opcion, self.total_positivos()),
                        'porcentaje_total': porcentaje(votos_opcion, self.votantes()),
                    }
                    for opcion, votos_opcion in votos_por_opcion.items()
                }
            }

        return OrderedDict(
            sorted(votos_positivos.items(), key=lambda partido: float(partido[1]["votos"]), reverse=True)
        )

    @lru_cache(128)
    def tabla_no_positivos(self):
        """
        Devuelve un diccionario con la cantidad de votos para cada una de las opciones no positivas.
        Incluye a todos los positivos agrupados como una única opción adicional.
        También incluye porcentajes calculados sobre el total de votos de la mesa.
        """
        # TODO Falta un criterio de ordenamiento para las opciones no positivas.
        tabla_no_positivos = {
            nombre_opcion: {
                "votos": votos,
                "porcentaje_total": porcentaje(votos, self.votantes())
            }
            for nombre_opcion, votos in self.resultados.votos_no_positivos.items()
        }

        # Esta key es especial porque la vista la muestra directamente en pantalla.
        tabla_no_positivos["Votos Positivos"] = {
            "votos": self.total_positivos(),
            "porcentaje_total": porcentaje(self.total_positivos(), self.votantes())
        }

        return tabla_no_positivos

    def electores(self):
        return self.resultados.electores

    def electores_en_mesas_escrutadas(self):
        return self.resultados.electores_en_mesas_escrutadas

    def porcentaje_mesas_escrutadas(self):
        return self.resultados.porcentaje_mesas_escrutadas

    def porcentaje_escrutado(self):
        return porcentaje(self.resultados.electores_en_mesas_escrutadas, self.resultados.electores)

    def porcentaje_participacion(self):
        return porcentaje(self.votantes(), self.resultados.electores_en_mesas_escrutadas)

    def total_mesas_escrutadas(self):
        return self.resultados.total_mesas_escrutadas

    def total_mesas(self):
        return self.resultados.total_mesas


class AvanceDeCarga(Sumarizador):
    """
    Esta clase contiene información sobre el avance de carga.
    """

    def __init__(self):
        super().__init__(
            tipo_de_agregacion=Sumarizador.TIPOS_DE_AGREGACIONES.todas_las_cargas,
            opciones_a_considerar=Sumarizador.OPCIONES_A_CONSIDERAR.todas,
            nivel_de_agregacion=None,
            ids_a_considerar=None
        )

    def mesas_con_o_sin_attachment(self, con_attachment):
        """
        Devuelve el conjunto de mesas de la categoría actual, con o sin attachment
        asociado (de acuerdo al parámetro con_attachment).
        """
        lookups = self.lookups_de_mesas()

        return Mesa.objects.filter(
            categorias=self.categoria,
            attachments__isnull=not con_attachment
        ).filter(lookups).distinct()

    @lru_cache(128)
    def cant_mesas_con_actas(self):
        return self.mesas_con_o_sin_attachment(True).count()

    def cant_actas_parcialmente_identificadas_por_origen(self):
        mesas_sin_attachment = self.mesas_con_o_sin_attachment(False)
        cant = Identificacion.objects.filter(
            status=Identificacion.STATUS.identificada,
            invalidada=False,
            mesa__in=Subquery(mesas_sin_attachment.values('pk'))
        ).values('source').annotate(count=Count('source'))

    @lru_cache(128)
    def cant_actas_parcialmente_identificadas(self, origen):
        """
        Devuelve la cantidad de actas parcialmente identificadas del origen parámetro.
        """
        for item in self.cant_actas_parcialmente_identificadas_por_origen():
            if item['source'] == origen:
                return item['count']

    # @lru_cache(128)
    # def cant_actas_con_identificacion_parcial(self):
    #     IdentificacionParcial.objects.filter(...)


    def calcular_mal(self):
        """
        Realiza los cálculos necesarios y devuelve un AttrDict con la info obtenida
        """
        mesas_sin_identificar = self.mesas_a_considerar.filter(attachments__isnull=True)

        mesacats_de_la_categoria = MesaCategoria.objects.filter(
            mesa__in=self.mesas_a_considerar,
            categoria=self.categoria
        )

        mesacats_sin_cargar = mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.sin_cargar) \
            .filter(mesa__attachments__isnull=False)

        mesacats_carga_parcial_sin_consolidar = \
            mesacats_de_la_categoria.filter(status = MesaCategoria.STATUS.parcial_sin_consolidar) | \
                mesacats_de_la_categoria.filter(status = MesaCategoria.STATUS.parcial_consolidada_csv)

        mesacats_carga_parcial_consolidada = \
            mesacats_de_la_categoria.filter(status = MesaCategoria.STATUS.parcial_consolidada_dc)

        mesacats_carga_total_sin_consolidar = \
            mesacats_de_la_categoria.filter(status = MesaCategoria.STATUS.total_sin_consolidar) | \
                mesacats_de_la_categoria.filter(status = MesaCategoria.STATUS.total_consolidada_csv)

        mesacats_carga_total_consolidada = \
            mesacats_de_la_categoria.filter(status = MesaCategoria.STATUS.total_consolidada_dc)

        mesacats_conflicto_o_problema = \
            mesacats_de_la_categoria.filter(status = MesaCategoria.STATUS.parcial_en_conflicto) | \
                mesacats_de_la_categoria.filter(status = MesaCategoria.STATUS.total_en_conflicto) | \
                    mesacats_de_la_categoria.filter(status = MesaCategoria.STATUS.con_problemas)

        dato_total = DatoTotalAvanceDeCarga().para_mesas(self.mesas_a_considerar)
        
        return AttrDict({
            "total": dato_total,
            "sin_identificar": DatoParcialAvanceDeCarga(dato_total).para_mesas(mesas_sin_identificar),
            "sin_cargar": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_sin_cargar),
            "carga_parcial_sin_consolidar": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_carga_parcial_sin_consolidar),
            "carga_parcial_consolidada": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_carga_parcial_consolidada),
            "carga_total_sin_consolidar": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_carga_total_sin_consolidar),
            "carga_total_consolidada": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_carga_total_consolidada),
            "conflicto_o_problema": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_conflicto_o_problema),
        })

        # mesacats_de_la_categoria = MesaCategoria.filter(
        #     mesa=OuterRef('pk'), categoria=self.categoria
        # )
        # self.mesas_a_considerar.filter(attachments__isnull=False) \ 
        #     .annotate(mesa_categoria=mesacats_de_la_categoria[:1]) \
        #         .filter(mesa_categoria.status=MesaCategoria.STATUS.sin_cargar)


    def get_resultados(self, categoria):
        """
        Realiza la contabilidad para la categoría, invocando al método ``calcular``.
        """
        self.categoria = categoria
        self.mesas_a_considerar = self.mesas(self.categoria)
        return AvanceWrapper(self.calcular())

    def calcular(self):
        dato_total = DatoTotalAvanceDeCarga().para_valores_fijos(1000, 50000)
        return AttrDict({
            "total": dato_total,
            "sin_identificar": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(200, 10000),
            "sin_cargar": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(200, 10000),
            "carga_parcial_sin_consolidar": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(200, 10000),
            "carga_parcial_consolidada": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(100, 5000),
            "carga_total_sin_consolidar": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(100, 5000),
            "carga_total_consolidada": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(100, 5000),
            "conflicto_o_problema": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(100, 5000),
        })


def porcentaje(parcial, total):
    """
    Función utilitaria para el cálculo de un porcentaje, así se hace igual en todos lados
    """
    return 0 if total == 0 else round((parcial * 100) / total, 2)


class DatoAvanceDeCarga():
    def para_mesas(self, mesas):
        self.la_cantidad_mesas = mesas.count()
        self.la_cantidad_electores = mesas.aggregate(v=Sum('electores'))['v'] or 0
        return self

    def para_mesacats(self, mesa_cats):
        self.la_cantidad_mesas = mesa_cats.count()
        self.la_cantidad_electores = mesa_cats.aggregate(v=Sum('mesa__electores'))['v'] or 0
        return self

    def para_valores_fijos(self, cantidad_mesas, cantidad_electores):
        self.la_cantidad_mesas = cantidad_mesas
        self.la_cantidad_electores = cantidad_electores
        return self

    def cantidad_mesas(self):
        return self.la_cantidad_mesas

    def cantidad_electores(self):
        return self.la_cantidad_electores


class DatoParcialAvanceDeCarga(DatoAvanceDeCarga):
    def __init__(self, dato_total):
        super().__init__()
        self.dato_total = dato_total

    def porcentaje_mesas(self):
        return porcentaje(self.cantidad_mesas(), self.dato_total.cantidad_mesas())

    def porcentaje_electores(self):
        return porcentaje(self.cantidad_electores(), self.dato_total.cantidad_electores())


class DatoTotalAvanceDeCarga(DatoAvanceDeCarga):
    def porcentaje_mesas(self):
        return 100.0

    def porcentaje_electores(self):
        return 100.0


class AvanceWrapper():
    def __init__(self, resultados):
        self.resultados = resultados
    
    def total(self):
        return self.resultados.total

    def sin_identificar(self):
        return self.resultados.sin_identificar

    def sin_cargar(self):
        return self.resultados.sin_cargar

    def carga_parcial_sin_consolidar(self):
        return self.resultados.carga_parcial_sin_consolidar

    def carga_parcial_consolidada(self):
        return self.resultados.carga_parcial_consolidada

    def carga_total_sin_consolidar(self):
        return self.resultados.carga_total_sin_consolidar

    def carga_total_consolidada(self):
        return self.resultados.carga_total_consolidada

    def conflicto_o_problema(self):
        return self.resultados.conflicto_o_problema



class Proyecciones(Sumarizador):
    """
    Esta clase encapsula el cómputo de proyecciones.
    """

    def __init__(self, tecnica, *args):
        self.tecnica = tecnica
        super().__init__(*args)

    def mesas_escrutadas(self):
        return self.mesas_a_considerar.filter(
            mesacategoria__categoria=self.categoria,
            mesacategoria__carga_testigo__isnull=False,
            **self.cargas_a_considerar_status_filter(self.categoria, 'mesacategoria__')
        )

    def total_electores(self, agrupacion):
        return (
            self.mesas_a_considerar.filter(
                circuito__in=Subquery(
                    AgrupacionCircuito.objects.filter(agrupacion__id=agrupacion.id
                                                      ).values_list('circuito_id', flat=True)
                )
            ).aggregate(electores=Sum('electores'))
        )['electores']

    def electores_en_mesas_escrutadas(self, agrupacion):
        return (
            self.mesas_escrutadas().filter(
                circuito__in=Subquery(
                    AgrupacionCircuito.objects.filter(agrupacion__id=agrupacion.id
                                                      ).values_list('circuito_id', flat=True)
                )
            ).aggregate(electores=Sum('electores'))
        )['electores']

    def agrupaciones_a_considerar(self, categoria, mesas):
        """
        Devuelve la lista de agrupaciones_a_considerar a considerar, descartando aquellas que no tienen aún
        el mínimo de mesas definido según la técnica de proyección.
        """
        mesas_por_agrupacion_subquery = (
            self.mesas_escrutadas().filter(circuito__id__in=OuterRef('circuitos')
                                           ).annotate(mesas_escrutadas=Count('pk')
                                                      ).values_list('mesas_escrutadas', flat=True)
        )

        return (
            AgrupacionCircuitos.objects.filter(proyeccion=self.tecnica).annotate(
                mesas_escrutadas=Subquery(mesas_por_agrupacion_subquery[:1], output_field=IntegerField())
            ).filter(minimo_mesas__lte=F('mesas_escrutadas'))
        )

    def coeficientes_para_proyeccion(self):
        return {
            agrupacion.id: self.total_electores(agrupacion) / self.electores_en_mesas_escrutadas(agrupacion)
            for agrupacion in self.agrupaciones_a_considerar(self.categoria, self.mesas_a_considerar)
        }

    def votos_por_opcion(self, categoria, mesas):
        """
        Dada una categoría y un conjunto de mesas, devuelve una tabla de resultados con la cantidad de
        votos por cada una de las opciones posibles (partidarias o no). A diferencia de la superclase,
        aquí se realiza el group_by también por AgrupacionCircuitos, filtrando sólo aquellas cargas
        correspondientes a agrupaciones que llegaron al mínimo de mesas requerido.
        """

        agrupaciones_subquery = Subquery(
            self.agrupaciones_a_considerar(categoria, mesas).filter(
                pk__in=(OuterRef('carga__mesa_categoria__mesa__circuito__agrupaciones'))
            ).values_list('id', flat=True)
        )

        return self.votos_reportados(categoria, mesas).values_list('opcion__id').annotate(
                id_agrupacion=agrupaciones_subquery
            ).exclude(
                id_agrupacion__isnull=True
            ).annotate(
                sum_votos=Sum('votos')
            ).values_list('opcion__id', 'id_agrupacion', 'sum_votos')

    def votos_por_agrupacion(self, votos_a_procesar):
        """
        Dada una lista de tuplas (id_opcion, id_agrupacion, sum_votos) los agrupa en un dictionary
        con key id_agrupacion y value = lista de tuplas (id_opcion, sum_votos)
        """
        votos_por_agrupacion = {}
        for id_opcion, id_agrupacion, sum_votos in votos_a_procesar:
            votos_por_agrupacion.setdefault(id_agrupacion, []).append((id_opcion, sum_votos))

        return votos_por_agrupacion

    def agrupar_votos(self, votos_a_procesar):
        coeficientes = self.coeficientes_para_proyeccion()
        votos_positivos_proyectados = {}
        votos_no_positivos_proyectados = {}

        for id_agrupacion, votos_de_agrupacion in self.votos_por_agrupacion(votos_a_procesar).items():
            votos_positivos, votos_no_positivos = super().agrupar_votos(votos_de_agrupacion)

            # Votos positivos
            for partido, votos_por_opcion in votos_positivos.items():
                votos_partido = votos_positivos_proyectados.setdefault(partido, {})
                for opcion, votos in votos_por_opcion.items():
                    votos_partido[opcion] = (
                        votos_partido.setdefault(opcion, 0) + round(votos * coeficientes[id_agrupacion])
                    )

            # Votos no positivos[opcion.nombre] = sum_votos if sum_votos else 0
            for nombre_opcion, votos in votos_no_positivos.items():
                votos_no_positivos_proyectados[nombre_opcion] = (
                    votos_no_positivos_proyectados.setdefault(nombre_opcion, 0) +
                    round(votos * coeficientes[id_agrupacion])
                )

        return votos_positivos_proyectados, votos_no_positivos_proyectados

    @classmethod
    def tecnicas_de_proyeccion(cls):
        return TecnicaProyeccion.objects.all()
