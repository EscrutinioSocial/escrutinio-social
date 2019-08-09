from django.conf import settings
from functools import lru_cache
from collections import OrderedDict
from attrdict import AttrDict
from django.db.models import Q, F, Sum, Subquery, OuterRef, Count, Exists
from .models import (
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
    AgrupacionCircuito,
    TIPOS_DE_AGREGACIONES,
    OPCIONES_A_CONSIDERAR,
    NIVELES_DE_AGREGACION,
)
from adjuntos.models import Identificacion, PreIdentificacion

NIVEL_DE_AGREGACION = {
    NIVELES_DE_AGREGACION.distrito: Distrito,
    NIVELES_DE_AGREGACION.seccion_politica: SeccionPolitica,
    NIVELES_DE_AGREGACION.seccion: Seccion,
    NIVELES_DE_AGREGACION.circuito: Circuito,
    NIVELES_DE_AGREGACION.lugar_de_votacion: LugarVotacion,
    NIVELES_DE_AGREGACION.mesa: Mesa
}


def create_sumarizador(
    parametros_sumarizacion=None,
    tecnica_de_proyeccion=None,
    configuracion_combinada=None,
    configuracion_distrito=None
):
    # Si nos llega una configuracion combinada creamos un SumarizadorIdem
    if configuracion_combinada:
        return SumarizadorCombinado(configuracion_combinada)

    # Si nos llega una configuracion por distrito tomamos su información
    if configuracion_distrito:
        tecnica_de_proyeccion = configuracion_distrito.proyeccion
        # En caso de no tener parámetros de sumarización, toda la info sale la conf
        if (parametros_sumarizacion is None):
            parametros_sumarizacion = [
                configuracion_distrito.agregacion,
                configuracion_distrito.opciones,
                NIVELES_DE_AGREGACION.distrito,
                [configuracion_distrito.distrito.id]
            ]
        # Otra opción es recibir el nivel de agregación y los ids a considerar en forma manual
        elif (len(parametros_sumarizacion) == 2):
            parametros_sumarizacion = [
                configuracion_distrito.agregacion,
                configuracion_distrito.opciones,
                *parametros_sumarizacion
            ]

    # En caso contrario se usa la técnica de proyección y parámetros recibidos.
    # Si hay una técnica de proyección se usa Proyecciones y si no se usa un Sumarizador normal.
    return Proyecciones(
        tecnica_de_proyeccion,
        *parametros_sumarizacion
    ) if tecnica_de_proyeccion else Sumarizador(*parametros_sumarizacion)


def porcentaje(numerador, denominador):
    """
    Expresa la razón numerador/denominador como un string correspondiente
    al porcentaje con 2 dígitos decimales.
    Si no puede calcularse, devuelve '-'.

    """
    if denominador and denominador > 0:
        return f'{numerador*100/denominador:.2f}'
    return '-'


def porcentaje_numerico(parcial, total):
    """
    Función utilitaria para el cálculo de un porcentaje, así se hace igual en todos lados
    """
    return 0 if total == 0 else round((parcial * 100) / total, 2)


class Sumarizador():
    """
    Esta clase encapsula el cómputo de resultados.
    """
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
        # Es una de TIPOS_DE_AGREGACIONES
        self.tipo_de_agregacion = tipo_de_agregacion

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

        if self.tipo_de_agregacion == TIPOS_DE_AGREGACIONES.solo_consolidados_doble_carga:
            if self.opciones_a_considerar == OPCIONES_A_CONSIDERAR.todas:
                lookups[f'{prefix}status'] = MesaCategoria.STATUS.total_consolidada_dc
            else:
                lookups[f'{prefix}status'] = MesaCategoria.STATUS.parcial_consolidada_dc

        elif self.tipo_de_agregacion == TIPOS_DE_AGREGACIONES.solo_consolidados:
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

        elif self.tipo_de_agregacion == TIPOS_DE_AGREGACIONES.todas_las_cargas:
            if self.opciones_a_considerar == OPCIONES_A_CONSIDERAR.todas:
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

        modelo = NIVEL_DE_AGREGACION.get(self.nivel_de_agregacion, None)
        if modelo:
            return modelo.objects.filter(id__in=self.ids_a_considerar)

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

    def mesas_escrutadas(self):
        """
        De las mesas incluidas en los filtros seleccionados, 
        aquellas que tienen votos para la categoría seleccionada.
        """
        return self.mesas_a_considerar.filter(
            mesacategoria__categoria=self.categoria,
            mesacategoria__carga_testigo__isnull=False,
            **self.cargas_a_considerar_status_filter(self.categoria, 'mesacategoria__')
        ).distinct()

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
        votos_reportados = VotoMesaReportado.objects.filter(
            carga__mesa_categoria__mesa__in=Subquery(mesas.values('id')),
            carga__mesa_categoria__categoria=categoria,
            carga__es_testigo__isnull=False,
            **self.cargas_a_considerar_status_filter(categoria)
        )

        return votos_reportados

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
                votos_no_positivos[opcion.nombre.lower()] = sum_votos if sum_votos else 0

        return votos_positivos, votos_no_positivos

    def calcular(self, categoria, mesas):
        """
        Implementa los cómputos esenciales de la categoría para las mesas dadas.
        Se invoca una vez para el cálculo de resultados y N veces para los proyectados.

        Devuelve
            electores: cantidad de electores en las mesas válidas de la categoría
            electores_en_mesas_escrutadas: cantidad de electores en las mesas efectivamente escrutadas
            votos: diccionario con resultados de votos por partido y opción (positivos y no positivos)
            total_positivos: total votos positivos
            total: total votos (positivos + no positivos)
        """

        # 1) Mesas.
        # Me quedo con las mesas que corresponden de acuerdo a los parámetros
        # y la categoría, que tengan la carga testigo para esa categoría.
        mesas_escrutadas = self.mesas_escrutadas()
        total_mesas_escrutadas = mesas_escrutadas.count()
        total_mesas = mesas.count()

        # 2) Electores.
        electores = mesas.filter(categorias=categoria).aggregate(v=Sum('electores'))['v'] or 0
        electores_en_mesas_escrutadas = mesas_escrutadas.aggregate(v=Sum('electores'))['v'] or 0

        # 3) Votos
        votos_por_opcion = self.votos_por_opcion(categoria, mesas)
        votos_positivos, votos_no_positivos = self.agrupar_votos(votos_por_opcion)

        return AttrDict({
            "total_mesas": total_mesas,
            "total_mesas_escrutadas": total_mesas_escrutadas,
            "electores": electores,
            "electores_en_mesas_escrutadas": electores_en_mesas_escrutadas,
            "votos_positivos": votos_positivos,
            "votos_no_positivos": votos_no_positivos,
        })

    def get_resultados(self, categoria):
        """
        Realiza la contabilidad para la categoría, invocando al método ``calcular``.
        """
        self.categoria = categoria
        self.mesas_a_considerar = self.mesas(categoria)
        return Resultados(self.opciones_a_considerar, self.calcular(categoria, self.mesas_a_considerar))


class ResultadosBase():
    """
    Clase base para el comportamiento común entre los resultados de una sumarización / proyección y 
    la sumatoria de muchos resultados en un ResultadoCombinado
    """
    def __init__(self, resultados):
        self.resultados = resultados

    def data(self):
        """
        Devuelve los datos de resultados 'crudos' para permitir que los distintos sumarizadores
        pasen información al template directamente sin obligar a que esta clase oficie de pasamanos.
        """
        return dict(self.resultados)

    @lru_cache(128)
    def tabla_positivos(self):
        """
        Devuelve toda la información sobre los votos positivos para mostrar.
        Para cada partido incluye:
            - votos: total de votos del partido
            - detalle: los votos de cada opción dentro del partido (recordar que
              es una PASO).
                Para cada opción incluye:
                    - votos: cantidad de votos para esta opción.
                    - porcentaje: porcentaje sobre el total del del partido.
                    - porcentaje_positivos: porcentaje sobre el total de votos
                      positivos.
                    - porcentaje_validos: porcentaje sobre el total de votos
                      positivos y en blanco.
                    - porcentaje_total: porcentaje sobre el total de votos.
        """
        votos_positivos = {}
        blancos = self.total_blancos() if self.total_blancos() != '-' else 0
        for partido, votos_por_opcion in self.resultados.votos_positivos.items():
            total_partido = sum(filter(None, votos_por_opcion.values()))
            votos_positivos[partido] = {
                'votos': total_partido,
                'porcentaje_positivos': porcentaje(total_partido, self.total_positivos()),
                'porcentaje_validos': porcentaje(total_partido, self.total_positivos() + blancos),
                'porcentaje_total': porcentaje(total_partido, self.votantes()),
                'detalle': {
                    opcion: {
                        'votos': votos_opcion,
                        'porcentaje': porcentaje(votos_opcion, total_partido),
                        'porcentaje_positivos': porcentaje(votos_opcion, self.total_positivos()),
                        'porcentaje_validos': porcentaje(votos_opcion, self.total_positivos() + blancos),
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
        tabla_no_positivos[settings.KEY_VOTOS_POSITIVOS] = {
            "votos": self.total_positivos(),
            "porcentaje_total": porcentaje(self.total_positivos(), self.votantes())
        }

        return tabla_no_positivos

    @lru_cache(128)
    def votantes(self):
        """
        Total de personas que votaron.
        """
        return self.total_positivos() + self.total_no_positivos()

    def electores(self):
        return self.resultados.electores

    def electores_en_mesas_escrutadas(self):
        return self.resultados.electores_en_mesas_escrutadas

    def porcentaje_mesas_escrutadas(self):
        return porcentaje(self.total_mesas_escrutadas(), self.total_mesas())

    def porcentaje_escrutado(self):
        return porcentaje(self.resultados.electores_en_mesas_escrutadas, self.resultados.electores)

    def porcentaje_participacion(self):
        return porcentaje(self.votantes(), self.resultados.electores_en_mesas_escrutadas)

    def total_mesas_escrutadas(self):
        return self.resultados.total_mesas_escrutadas

    def total_mesas(self):
        return self.resultados.total_mesas

    def total_blancos(self):
        return self.resultados.votos_no_positivos.get(settings.OPCION_BLANCOS['nombre'], '-')

    def total_nulos(self):
        return self.resultados.votos_no_positivos.get(settings.OPCION_NULOS['nombre'], '-')

    def total_votos(self):
        return self.resultados.votos_no_positivos.get(settings.OPCION_TOTAL_VOTOS['nombre'], '-')

    def total_sobres(self):
        return self.resultados.votos_no_positivos.get(settings.OPCION_TOTAL_SOBRES['nombre'], '-')

    def porcentaje_positivos(self):
        return porcentaje(self.total_positivos(), self.votantes())

    def porcentaje_blancos(self):
        blancos = self.total_blancos()
        return porcentaje(blancos, self.votantes()) if blancos != '-' else '-'

    def porcentaje_nulos(self):
        nulos = self.total_nulos()
        return porcentaje(nulos, self.votantes()) if nulos != '-' else '-'


class Resultados(ResultadosBase):
    """
    Esta clase contiene los resultados de una sumarización o proyección.
    """

    def __init__(self, opciones_a_considerar, resultados):
        super().__init__(resultados)
        self.opciones_a_considerar = opciones_a_considerar

    @lru_cache(128)
    def total_positivos(self):
        """
        Devuelve el total de votos positivos, sumando los votos de cada una de las opciones de cada partido
        en el caso self.opciones_a_considerar == OPCIONES_A_CONSIDERAR.todas.

        En el caso self.self.opciones_a_considerar == OPCIONES_A_CONSIDERAR.prioritarias
        obtiene la opción de total
        """
        if self.opciones_a_considerar == OPCIONES_A_CONSIDERAR.todas:
            total_positivos = sum(
                sum(votos for votos in opciones_partido.values() if votos)
                for opciones_partido in self.resultados.votos_positivos.values()
            )
        else:
            nombre_opcion_total = Opcion.total_votos().nombre
            total = self.resultados.votos_no_positivos[nombre_opcion_total]
            total_no_positivos = self.total_no_positivos()
            total_positivos = max(total - total_no_positivos, 0)

        return total_positivos

    @lru_cache(128)
    def total_no_positivos(self):
        """
        Devuelve el total de votos no positivos, sumando los votos a cada opción no partidaria
        y excluyendo la opción que corresponde a totales (como el total de votantes o de sobres).
        """
        nombre_opcion_total = Opcion.total_votos().nombre
        nombre_opcion_sobres = Opcion.sobres().nombre
        return sum(
            votos for opcion, votos in self.resultados.votos_no_positivos.items()
            if opcion not in (nombre_opcion_total, nombre_opcion_sobres)
        )


class ResultadoCombinado(ResultadosBase):
    _total_positivos = 0
    _total_no_positivos = 0

    def __init__(self):
        super().__init__(AttrDict({
            'total_mesas': 0,
            'total_mesas_escrutadas': 0,
            'electores': 0,
            'electores_en_mesas_escrutadas': 0,
            'votos_positivos': {},

            'votos_no_positivos': {opcion['nombre']: 0 for opcion in [
                settings.OPCION_BLANCOS,
                settings.OPCION_NULOS,
                settings.OPCION_TOTAL_VOTOS,
                settings.OPCION_TOTAL_SOBRES,
            ]}
        }))

    def __add__(self, other):
        self._total_positivos += other.total_positivos()
        self._total_no_positivos += other.total_no_positivos()

        # Sumar los votos no positivos
        self.resultados.votos_no_positivos = {
            key: value + other.resultados.votos_no_positivos.get(key, 0)
            for key, value in self.resultados.votos_no_positivos.items()
        }

        self.resultados.votos_positivos = {
            partido: {
                opcion: votos_opcion + self.resultados.votos_positivos.get(partido, {}).get(opcion, 0)
                for opcion, votos_opcion in votos_partido.items()
            }
            for partido, votos_partido in other.resultados.votos_positivos.items()
        }
        print(self.resultados.votos_positivos)

        # Sumar el resto de los atributos en resultados
        for attr in ['total_mesas', 'total_mesas_escrutadas', 'electores', 'electores_en_mesas_escrutadas']:
            self.resultados[attr] += other.resultados[attr]

        # TODO falta pasar agrupaciones no consideradas

        return self

    def total_positivos(self):
        return self._total_positivos

    def total_no_positivos(self):
        return self._total_no_positivos


class AvanceDeCarga(Sumarizador):
    """
    Esta clase contiene información sobre el avance de carga.
    """

    def __init__(
        self,
        nivel_de_agregacion=None,
        ids_a_considerar=None
    ):
        super().__init__(
            tipo_de_agregacion=TIPOS_DE_AGREGACIONES.todas_las_cargas,
            opciones_a_considerar=OPCIONES_A_CONSIDERAR.todas,
            nivel_de_agregacion=nivel_de_agregacion,
            ids_a_considerar=ids_a_considerar
        )

    def lookups_de_preidentificaciones(self):
        lookups = Q()
        if self.filtros:
            if self.filtros.model is Distrito:
                lookups = Q(distrito__in=self.filtros)

            elif self.filtros.model is Seccion:
                lookups = Q(seccion__in=self.filtros)

            elif self.filtros.model is Circuito:
                lookups = Q(circuito__in=self.filtros)

            elif self.filtros.model is SeccionPolitica or self.filtros.model is LugarVotacion or self.filtros.model is Mesa:
                lookups = None

        return lookups

    def calcular(self):
        """
        Realiza los cálculos necesarios y devuelve un AttrDict con la info obtenida
        """
        # con preidentificación: depende de las preidentificaciones correspondientes a la unidad geográfica,
        # esto no depende de las mesas
        # ... puede haber más preidentificaciones que mesas, si hay dos fotos por mesa
        # por eso no se informa porcentaje
        cantidad_preidentificaciones = 0
        lookups_preident = self.lookups_de_preidentificaciones()
        if lookups_preident is not None:
            cantidad_preidentificaciones = PreIdentificacion.objects.filter(lookups_preident).count()

        # mesas sin identificar y en identificación: dependen de las identificaciones **válidas**
        # y de los attachment
        identificaciones_validas_mesa = Identificacion.objects.filter(mesa=OuterRef('pk'), invalidada=False)
        mesas_con_marca_identificacion = self.mesas_a_considerar.annotate(
            tiene_identificaciones=Exists(identificaciones_validas_mesa))
        mesas_sin_identificar = mesas_con_marca_identificacion.filter(tiene_identificaciones=False)
        mesas_en_identificacion = mesas_con_marca_identificacion.filter(
            tiene_identificaciones=True, attachments__isnull=True)

        mesacats_de_la_categoria = MesaCategoria.objects.filter(
            mesa__in=self.mesas_a_considerar,
            categoria=self.categoria
        )

        mesacats_sin_cargar = mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.sin_cargar) \
            .filter(mesa__attachments__isnull=False)

        mesacats_carga_parcial_sin_consolidar = \
            mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.parcial_sin_consolidar) | \
                mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.parcial_consolidada_csv)

        mesacats_carga_parcial_consolidada = \
            mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.parcial_consolidada_dc)

        mesacats_carga_total_sin_consolidar = \
            mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.total_sin_consolidar) | \
                mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.total_consolidada_csv)

        mesacats_carga_total_consolidada = \
            mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.total_consolidada_dc)

        mesacats_conflicto_o_problema = \
            mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.parcial_en_conflicto) | \
                mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.total_en_conflicto) | \
                    mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.con_problemas)

        dato_total = DatoTotalAvanceDeCarga().para_mesas(self.mesas_a_considerar)

        return AttrDict({
            "total": dato_total,
            "sin_identificar": DatoParcialAvanceDeCarga(dato_total).para_mesas(mesas_sin_identificar),
            "en_identificacion": DatoParcialAvanceDeCarga(dato_total).para_mesas(mesas_en_identificacion),
            "sin_cargar": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_sin_cargar),
            "carga_parcial_sin_consolidar": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_carga_parcial_sin_consolidar),
            "carga_parcial_consolidada": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_carga_parcial_consolidada),
            "carga_total_sin_consolidar": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_carga_total_sin_consolidar),
            "carga_total_consolidada": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_carga_total_consolidada),
            "conflicto_o_problema": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_conflicto_o_problema),
            "preidentificaciones": cantidad_preidentificaciones
        })

    def get_resultados(self, categoria):
        """
        Realiza la contabilidad para la categoría, invocando al método ``calcular``.
        """
        self.categoria = categoria
        self.mesas_a_considerar = self.mesas(self.categoria)
        return AvanceWrapper(self.calcular())

    def calcular_fake(self):
        """
        Este lo usé para que se pudiera desarrollar el frontend mientras resolvía esta clase.
        Lo dejo por eventuales refactors.
        """
        dato_total = DatoTotalAvanceDeCarga().para_valores_fijos(1000, 50000)
        return AttrDict({
            "total": dato_total,
            "sin_identificar": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(200, 10000),
            "en_identificacion": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(50, 2000),
            "sin_cargar": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(150, 8000),
            "carga_parcial_sin_consolidar": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(200, 10000),
            "carga_parcial_consolidada": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(100, 5000),
            "carga_total_sin_consolidar": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(100, 5000),
            "carga_total_consolidada": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(100, 5000),
            "conflicto_o_problema": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(100, 5000),
        })


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
        return porcentaje_numerico(self.cantidad_mesas(), self.dato_total.cantidad_mesas())

    def porcentaje_electores(self):
        return porcentaje_numerico(self.cantidad_electores(), self.dato_total.cantidad_electores())


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

    def en_identificacion(self):
        return self.resultados.en_identificacion

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

    def preidentificaciones(self):
        return self.resultados.preidentificaciones


class Proyecciones(Sumarizador):
    """
    Esta clase encapsula el cómputo de proyecciones.
    """
    def __init__(self, tecnica, *args):
        self.tecnica = tecnica
        super().__init__(*args)

    def circuito_subquery(self, id_agrupacion):
        """
        Construye un subquery que permite filtrar mesas por id_agrupacion
        """
        return Subquery(AgrupacionCircuito.objects.filter(
            agrupacion__id=id_agrupacion).values_list('circuito_id', flat=True))

    def total_electores(self, id_agrupacion):
        """
        Calcula el total de electores en una agrupación de circuitos
        """
        return self.mesas_a_considerar.filter(
            circuito__in=self.circuito_subquery(id_agrupacion)
        ).aggregate(electores=Sum('electores'))['electores']

    def electores_en_mesas_escrutadas(self, id_agrupacion):
        """
        Calcula el total de electores en las mesas escrutadas de una agrupación de circuitos
        """
        return self.mesas_escrutadas().filter(
            circuito__in=self.circuito_subquery(id_agrupacion)
        ).aggregate(electores=Sum('electores'))['electores']

    def total_mesas(self, id_agrupacion):
        """
        Calcula el total de mesas en una agrupación de circuitos
        """
        return self.mesas_a_considerar.filter(circuito__in=self.circuito_subquery(id_agrupacion)).count()

    def cant_mesas_escrutadas(self, id_agrupacion):
        """
        Calcula el total de electores en las mesas escrutadas de una agrupación de circuitos
        """
        return self.mesas_escrutadas().filter(circuito__in=self.circuito_subquery(id_agrupacion)).count()

    def coeficiente_para_proyeccion(self, id_agrupacion):
        """
        Devuelve el coeficiente o factor de ponderación para una agrupación de circuitos.
        Idealmente debería surgir de la división entre la totalidad de votantes en la agrupación, 
        dividido por la cantidad de votantes en las mesas escrutadas, pero ante la imposibilidad
        de contar con esos datos estamos dividiendo directamente la cantidad de mesas.
        """
        # TODO Considerar ambas formas de proyectar y hacerlo configurable para los distritos
        # en los que se cuente con la información de electores por mesa.
        # return self.total_electores(id_agrupacion) / self.electores_en    _mesas_escrutadas(id_agrupacion)
        return self.total_mesas(id_agrupacion) / self.cant_mesas_escrutadas(id_agrupacion)

    @lru_cache(128)
    def agrupaciones_no_consideradas(self):
        """
        Devuelve la lista de agrupaciones que fueron descartadas por no tener el mínimo de mesas exigido.

        Atención: el query se realiza en realidad sobre AgrupacionCircuito, porque de otra manera la
        many to many entre AgrupacionCircuitos y Circuito impide hacer agregaciones.
        """

        return AgrupacionCircuito.objects.values("agrupacion").annotate(
            mesas_escrutadas=Count(
                "circuito__mesas",
                filter=Q(circuito__mesas__id__in=self.mesas_escrutadas().values_list('id', flat=True))
            )
        ).filter(agrupacion__minimo_mesas__gt=F('mesas_escrutadas')).values_list(
            'agrupacion__nombre', 'agrupacion__minimo_mesas', 'mesas_escrutadas'
        )

    @lru_cache(128)
    def agrupaciones_a_considerar_raw(self):
        """
        Devuelve la lista de agrupaciones que se incluyen en la proyección, descartando aquellas
        que no tienen aún el mínimo de mesas definido según la técnica de proyección.

        Atención: el query se realiza en realidad sobre AgrupacionCircuito, porque de otra manera la
        many to many entre AgrupacionCircuitos y Circuito impide hacer agregaciones.
        """

        return AgrupacionCircuito.objects.values("agrupacion").annotate(
            mesas_escrutadas=Count(
                "circuito__mesas",
                filter=Q(circuito__mesas__id__in=self.mesas_escrutadas().values_list('id', flat=True))
            )
        ).filter(agrupacion__minimo_mesas__lte=F('mesas_escrutadas'))

    def agrupaciones_a_considerar(self):
        """
        Idem anterior pero devuelve sólo ids de agrupación.
        """
        return self.agrupaciones_a_considerar_raw().values_list('agrupacion', flat=True)

    def cant_mesas_escrutadas_y_consideradas(self):
        """
        Devuelve la cantidad final de mesas que se utilizaron en la proyección, puede ser menor a lo
        escrutado cuando una agrupación de circuitos tiene menos mesas escrutadas de las necesarias
        para ser consideradas en la proyección.
        """
        return self.agrupaciones_a_considerar_raw().aggregate(cant=Sum('mesas_escrutadas'))['cant']

    def coeficientes_para_proyeccion(self):
        return {
            id_agrupacion: self.coeficiente_para_proyeccion(id_agrupacion)
            for id_agrupacion in self.agrupaciones_a_considerar()
        }

    def votos_por_opcion(self, categoria, mesas):
        """
        Dada una categoría y un conjunto de mesas, devuelve una tabla de resultados con la cantidad de
        votos por cada una de las opciones posibles (partidarias o no). A diferencia de la superclase,
        aquí se realiza el group_by también por AgrupacionCircuitos, filtrando sólo aquellas cargas
        correspondientes a agrupaciones que llegaron al mínimo de mesas requerido.
        """

        agrupaciones_subquery = self.agrupaciones_a_considerar().filter(
            agrupacion__in=(OuterRef('carga__mesa_categoria__mesa__circuito__agrupaciones'))
        ).values_list('agrupacion', flat=True)

        return self.votos_reportados(categoria, mesas).values_list('opcion__id').annotate(
            id_agrupacion=Subquery(agrupaciones_subquery)
        ).exclude(id_agrupacion__isnull=True).annotate(
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

    def calcular(self, categoria, mesas):
        """
        Extiende los cómputos del sumarizador para agregar las agrupaciones que no fueron consideradas en la
        proyección por no alcanzar el mínimo de mesas requerido.
        """
        computos = super().calcular(categoria, mesas)
        computos.total_mesas_escrutadas = self.cant_mesas_escrutadas_y_consideradas()
        computos.agrupaciones_no_consideradas = self.agrupaciones_no_consideradas()

        return computos

    @classmethod
    def tecnicas_de_proyeccion(cls):
        return TecnicaProyeccion.objects.all()


class SumarizadorCombinado():

    def __init__(self, configuracion):
        self.configuracion = configuracion

    @property
    def filtros(self):
        """
        El sumarizador combinado siempre es para el total país.
        """
        return

    def mesas(self, categoria):
        """
            Devuelve todas las mesas para la categoría especificada
        """
        return Mesa.objects.filter(categorias=categoria).distinct()

    def get_resultados(self, categoria):
        return sum((
            create_sumarizador(configuracion_distrito=configuracion_distrito).get_resultados(categoria)
            for configuracion_distrito in self.configuracion.configuraciones.all()
        ), ResultadoCombinado())
