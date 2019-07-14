import itertools
from django.conf import settings
from functools import lru_cache
from collections import defaultdict, OrderedDict
from attrdict import AttrDict
from functools import lru_cache

class Resultados():
    """
    Esta clase encapsula el cómputo de resultados.
    """

    def __init__(self, kwargs, tipo_de_computo):
        """
        El tipo de cómputo indica qué datos se tienen en cuenta y cuáles no.
        """
        self.kwargs = kwargs
        self.tipo_de_computo = tipo_de_computo

    @lru_cache(128)
    def status_filter(self, categoria, prefix='carga__mesa_categoria__'):
        lookups = dict()
        if self.kwargs['status'] == 'tc':
            lookups[f'{prefix}status'] = MesaCategoria.STATUS.total_confirmada
        elif self.kwargs['status'] == 'tsc':
            # incluye confirmados y sin confirmar
            lookups[f'{prefix}status__in'] = (
                MesaCategoria.STATUS.total_confirmada,
                MesaCategoria.STATUS.total_sin_confirmar,
            )
        elif self.kwargs['status'] == 'pc':
            # total confirmada incluye a parcial
            # total sin confirmar asume que hubo parcial confirmada. Revisar
            lookups[f'{prefix}status__in'] = (
                MesaCategoria.STATUS.total_confirmada,
                MesaCategoria.STATUS.total_sin_confirmar,
                MesaCategoria.STATUS.parcial_confirmada,
            )
        elif self.kwargs['status'] == 'psc':
            # parciales sin confirmar no requieren filtro
            # dado que se computa cualquier carga testigo.
            pass
        return lookups

    def agregaciones_por_partido(self, categoria):
        """
        Dada una categoria, devuelve los criterios de agregación
        aplicados a VotoMesaReporto para obtener una "tabla de resultados"
        que incluye agregaciones por partido politico (considerados positivos)
        y otros no positivos

        Se utilizan expresiones condicionales. Referencia

        https://docs.djangoproject.com/en/2.2/ref/models/conditional-expressions/
        """
        sum_por_partido = {}
        otras_opciones = {}
        status_lookups = self.status_filter(categoria)

        for id in Partido.objects.filter(
            opciones__categorias__id=categoria.id
        ).distinct().values_list('id', flat=True):
            sum_por_partido[str(id)] = Sum(
                Case(
                    When(
                        opcion__partido__id=id,
                        carga__mesa_categoria__categoria=categoria,
                        carga__es_testigo__isnull=False,
                        then=F('votos'),
                        **status_lookups

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
                        carga__mesa_categoria__categoria=categoria,
                        carga__es_testigo__isnull=False,
                        then=F('votos'),
                        **status_lookups
                    ), output_field=IntegerField()
                )
            )
        return sum_por_partido, otras_opciones

    @property
    def filtros(self, kwargs):
        """
        A partir de los argumentos de urls, devuelve
        listas de sección, circuito ,etc. para filtrar
        """
        numero = self.kwargs.get('numero')
        listado = self.kwargs.get('listado')
        tipo = self.kwargs.get('tipo')

        if numero:
            # Pidieron una sola.

            if tipo == 'distrito':
                return Distrito.objects.filter(numero=numero)

            elif tipo == 'seccion':
                return Seccion.objects.filter(numero=numero)

            elif tipo == 'circuito':
                return Circuito.objects.filter(numero=numero)

            elif tipo == 'lugarvotacion':
                return LugarVotacion.objects.filter(numero=numero)

            elif tipo == 'mesa':
                return Mesa.objects.filter(numero=numero)
        elif listado:
            # Pidieron varias.

            if tipo == 'distrito':
                return Distrito.objects.filter(id__in=listado)

            elif tipo == 'seccion':
                return Seccion.objects.filter(id__in=listado)

            elif tipo == 'circuito'
                return Circuito.objects.filter(id__in=listado)

            elif tipo == 'lugarvotacion':
                return LugarVotacion.objects.filter(id__in=listado)

            elif tipo == 'mesa':
               return Mesa.objects.filter(id__in=listado)

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
                lookups = Q(lugar_votacion__circuito__seccion__distrito__in=self.filtros)

            if self.filtros.model is Seccion:
                lookups = Q(lugar_votacion__circuito__seccion__in=self.filtros)

            elif self.filtros.model is Circuito:
                lookups = Q(lugar_votacion__circuito__in=self.filtros)

            elif 'lugarvotacion' in self.request.GET:
                lookups = Q(lugar_votacion__id__in=self.filtros)

            elif 'mesa' in self.request.GET:
                lookups = Q(id__in=self.filtros)

        return Mesa.objects.filter(categorias=categoria).filter(lookups).distinct()

    @lru_cache(128)
    def electores(self, categoria):
        """
        devuelve el número de electores para :meth:`~.mesas`

        TODO: convertir esto en un método de ``MesaManager``
        """
        mesas = self.mesas(categoria)
        electores = mesas.aggregate(v=Sum('electores'))['v']
        return electores or 0

    def get_resultados(self, categoria, proyectado):
        """
        Realiza la contabilidad para la categoría, invocando al método
        ``calcular``.

        Si el se pasa el parámetro proyectado, se incluye un diccionario
        extra con la ponderación, invocando a ``calcular`` para obtener los
        resultados parciales de cada subdistrito para luego realizar la ponderación.
        """
        lookups = Q()
        lookups2 = Q()
        resultados = {}

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
        electores = mesas.filter(categorias=categoria).aggregate(v=Sum('electores'))['v'] or 0
        sum_por_partido, otras_opciones = self.agregaciones_por_partido(categoria)

        # primero para partidos
        reportados = VotoMesaReportado.objects.filter(
            carga__mesa_categoria__mesa__in=Subquery(mesas.values('id')),
            carga__es_testigo__isnull=False,
            **self.status_filter(categoria)
        )
        mesas_escrutadas = mesas.filter(
            mesacategoria__categoria=categoria,
            mesacategoria__carga_testigo__isnull=False,
            **self.status_filter(categoria, 'mesacategoria__')
        ).distinct()
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

    @classmethod
    def get_tipos_sumarizacion(cls):
        """
        Esto debería cambiarse cuando se realice el issue 17.
        Por ahora va a ser hardcodeado
        """
        return [{'pk': '1', 'name': 'Normal'}, {'pk': '2', 'name': 'Proyectado'}]