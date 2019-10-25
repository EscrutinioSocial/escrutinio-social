from functools import lru_cache
from django.db.models import Q, F, Sum, Subquery, OuterRef, Count
from .models import (
    Categoria,
    Mesa,
    MesaCategoria,
    TecnicaProyeccion,
    AgrupacionCircuito,
    AgrupacionCircuitos,
    NIVELES_DE_AGREGACION,
)
from .resultados import ResultadoCombinado
from .sumarizador import Sumarizador

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

    def cant_mesas_por_agrupacion(self):
        """
        Devuelve la lista de agrupaciones que se incluyen en la proyección, descartando aquellas
        que no tienen aún el mínimo de mesas definido según la técnica de proyección.
        """

        # Era self.mesas_a_considerar, copiado para optimizar query por MesaCategoria que es más eficiente
        # que por mesa, la optimización podria venirle bien también al sumarizador, pero prefiero no meter
        # ese refactor a 3 días del escrutinio.
        lookups = self.lookups_de_mesas("mesa__")
        mcs_a_considerar = MesaCategoria.objects.filter(categoria=self.categoria).filter(**lookups)

        # Era self.mesas_escrutadas, copiado por el mismo motivo.
        mcs_escrutadas = mcs_a_considerar.filter(
            carga_testigo__isnull=False,
            **self.cargas_a_considerar_status_filter(self.categoria, '')
        )

        cant_mesas_por_circuito = dict(mcs_escrutadas.values_list('mesa__circuito').annotate(
            cant_mesas=Count('mesa__circuito')
        ))

        agrupaciones = AgrupacionCircuitos.objects.filter(
            proyeccion=self.tecnica
        ).prefetch_related('circuitos')

        return ((
            agrupacion,
            sum(cant_mesas_por_circuito.get(circuito.id, 0) for circuito in agrupacion.circuitos.all())
        ) for agrupacion in agrupaciones)

    def agrupaciones_a_considerar(self):
        return list(
            agrupacion.id for (agrupacion, cant_mesas) in self.cant_mesas_por_agrupacion()
            if cant_mesas >= agrupacion.minimo_mesas
        )

    def cant_mesas_escrutadas_y_consideradas(self):
        """
        Devuelve la cantidad final de mesas que se utilizaron en la proyección, puede ser menor a lo
        escrutado cuando una agrupación de circuitos tiene menos mesas escrutadas de las necesarias
        para ser consideradas en la proyección.
        """
        return sum(cant_mesas for (_, cant_mesas) in self.cant_mesas_por_agrupacion())

    def coeficientes_para_proyeccion(self):
        coeficientes = {
            id_agrupacion: self.coeficiente_para_proyeccion(id_agrupacion)
            for id_agrupacion in self.agrupaciones_a_considerar()
        }
        return coeficientes

    def votos_por_opcion(self, categoria, mesas):
        """
        Dada una categoría y un conjunto de mesas, devuelve una tabla de resultados con la cantidad de
        votos por cada una de las opciones posibles (partidarias o no). A diferencia de la superclase,
        aquí se realiza el group_by también por AgrupacionCircuitos, filtrando sólo aquellas cargas
        correspondientes a agrupaciones que llegaron al mínimo de mesas requerido.
        """

        agrupaciones_subquery = AgrupacionCircuitos.objects.filter(
            id__in=self.agrupaciones_a_considerar()
        ).filter(id__in=(OuterRef('carga__mesa_categoria__mesa__circuito__agrupaciones'))
                 ).values_list('id', flat=True)

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

    def categorias(self):
        return Categoria.objects.filter(distrito__isnull=True, activa=True)
