from django.db.models import Q, Sum, OuterRef, Exists
from attrdict import AttrDict
from .models import (
    Distrito,
    SeccionPolitica,
    Seccion,
    Circuito,
    LugarVotacion,
    MesaCategoria,
    Mesa,
    TIPOS_DE_AGREGACIONES,
    OPCIONES_A_CONSIDERAR,
)
from .resultados import porcentaje_numerico
from .sumarizador import Sumarizador
from adjuntos.models import Identificacion, PreIdentificacion


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
        # Nota previa: se elige mirar siempre status de la mesacat, nunca existencia o inexistencia de cargas
        # de esta forma, el reporte es internamente coherente.
        # Tener en cuenta que puede haber mesacats con cargas y status "sin_cargar",
        # porque todavía no corrió la consolidación que le cambia el status.
        # Carlos Lombardi, 2019.08.10

        # con preidentificación: depende de las preidentificaciones correspondientes a la unidad geográfica,
        # esto no depende de las mesas
        # ... puede haber más preidentificaciones que mesas, si hay dos fotos por mesa
        # por eso no se informa porcentaje
        cantidad_preidentificaciones = 0
        lookups_preident = self.lookups_de_preidentificaciones()
        if lookups_preident is not None:
            cantidad_preidentificaciones = PreIdentificacion.objects.filter(lookups_preident).count()


        mesacats_de_la_categoria = MesaCategoria.objects.filter(
            mesa__in=self.mesas_a_considerar,
            categoria=self.categoria
        )

        # mesas sin identificar y en identificación: dependen de las identificaciones **válidas**
        # y de los attachment.
        # respecto de la condición "mesa__attachments=None" ver comentario abajo, 
        # en la definición de mesacats_sin_cargar
        identificaciones_validas_mesacat = Identificacion.objects.filter(mesa=OuterRef('mesa'), invalidada=False)
        mesacats_con_marca_identificacion = mesacats_de_la_categoria.annotate(
            tiene_identificaciones=Exists(identificaciones_validas_mesacat))
        mesacats_sin_identificar = mesacats_con_marca_identificacion.filter(
            tiene_identificaciones=False)
        mesacats_sin_identificar_sin_cargas = mesacats_sin_identificar.filter(status=MesaCategoria.STATUS.sin_cargar)
        mesacats_sin_identificar_con_cargas = mesacats_sin_identificar.exclude(status=MesaCategoria.STATUS.sin_cargar)
        mesacats_en_identificacion = mesacats_con_marca_identificacion.filter(
            tiene_identificaciones=True, mesa__attachments=None)
        mesacats_en_identificacion_sin_cargas = mesacats_en_identificacion.filter(
            status=MesaCategoria.STATUS.sin_cargar)
        mesacats_en_identificacion_con_cargas = mesacats_en_identificacion.exclude(
            status=MesaCategoria.STATUS.sin_cargar)
        

        # mesas sin identificar y en identificación: dependen de las identificaciones **válidas**
        # y de los attachment
        # identificaciones_validas_mesa = Identificacion.objects.filter(mesa=OuterRef('pk'), invalidada=False)
        # mesas_con_marca_identificacion = self.mesas_a_considerar.annotate(
        #     tiene_identificaciones=Exists(identificaciones_validas_mesa))
        # mesas_sin_identificar = mesas_con_marca_identificacion.filter(
        #     tiene_identificaciones=False)
        # mesas_en_identificacion = mesas_con_marca_identificacion.filter(
        #     tiene_identificaciones=True, attachments=None)

        # como "a cargar" se reportan solamente los que tienen attachments
        # OJO hay que hacer .exclude(mesa__attachments=None), si el query se arma distinto
        # se corre el peligro de que una mesa con N attachments con N > 1 (lo que es válido en esta app) cuente N veces.
        # Carlos Lombardi, 9/8/2019
        mesacats_sin_cargar = mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.sin_cargar) \
            .exclude(mesa__attachments=None)

        mesacats_carga_parcial_sin_consolidar = \
            mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.parcial_sin_consolidar) 

        mesacats_carga_parcial_consolidada_csv = \
            mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.parcial_consolidada_csv)

        mesacats_carga_parcial_consolidada_dc = \
            mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.parcial_consolidada_dc)

        mesacats_carga_total_sin_consolidar = \
            mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.total_sin_consolidar)
                
        mesacats_carga_total_consolidada_csv = \
            mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.total_consolidada_csv)

        mesacats_carga_total_consolidada_dc = \
            mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.total_consolidada_dc)

        mesacats_conflicto_o_problema = \
            mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.parcial_en_conflicto) | \
                mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.total_en_conflicto) | \
                    mesacats_de_la_categoria.filter(status=MesaCategoria.STATUS.con_problemas)

        dato_total = DatoTotalAvanceDeCarga().para_mesas(self.mesas_a_considerar)

        return AttrDict({
            "total": dato_total,
            "sin_identificar_sin_cargas": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_sin_identificar_sin_cargas),
            "sin_identificar_con_cargas": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_sin_identificar_con_cargas),
            "en_identificacion_sin_cargas": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_en_identificacion_sin_cargas),
            "en_identificacion_con_cargas": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_en_identificacion_con_cargas),
            "sin_cargar": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_sin_cargar),
            "carga_parcial_sin_consolidar": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_carga_parcial_sin_consolidar),
            "carga_parcial_consolidada_csv": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_carga_parcial_consolidada_csv),
            "carga_parcial_consolidada_dc": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_carga_parcial_consolidada_dc),
            "carga_total_sin_consolidar": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_carga_total_sin_consolidar),
            "carga_total_consolidada_csv": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_carga_total_consolidada_csv),
            "carga_total_consolidada_dc": DatoParcialAvanceDeCarga(dato_total).para_mesacats(mesacats_carga_total_consolidada_dc),
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
        resultado_bruto = AttrDict({
            "total": dato_total,
            "sin_identificar_sin_cargas": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(200, 10000),
            "sin_identificar_con_cargas": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(0, 0),
            "en_identificacion_sin_cargas": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(50, 2000),
            "en_identificacion_con_cargas": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(0, 0),
            "sin_cargar": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(150, 8000),
            "carga_parcial_sin_consolidar": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(200, 10000),
            "carga_parcial_consolidada_csv": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(50, 3000),
            "carga_parcial_consolidada_dc": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(50, 2000),
            "carga_total_sin_consolidar": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(100, 5000),
            "carga_total_consolidada_csv": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(50, 3000),
            "carga_total_consolidada_dc": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(50, 2000),
            "conflicto_o_problema": DatoParcialAvanceDeCarga(dato_total).para_valores_fijos(100, 5000),
        })
        return AvanceWrapper(resultado_bruto)


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

    def sin_identificar_sin_cargas(self):
        return self.resultados.sin_identificar_sin_cargas

    def sin_identificar_con_cargas(self):
        return self.resultados.sin_identificar_con_cargas

    def en_identificacion_sin_cargas(self):
        return self.resultados.en_identificacion_sin_cargas

    def en_identificacion_con_cargas(self):
        return self.resultados.en_identificacion_con_cargas

    def sin_cargar(self):
        return self.resultados.sin_cargar

    def carga_parcial_sin_consolidar(self):
        return self.resultados.carga_parcial_sin_consolidar

    def carga_parcial_consolidada_csv(self):
        return self.resultados.carga_parcial_consolidada_csv

    def carga_parcial_consolidada_dc(self):
        return self.resultados.carga_parcial_consolidada_dc

    def carga_total_sin_consolidar(self):
        return self.resultados.carga_total_sin_consolidar

    def carga_total_consolidada_csv(self):
        return self.resultados.carga_total_consolidada_csv

    def carga_total_consolidada_dc(self):
        return self.resultados.carga_total_consolidada_dc

    def conflicto_o_problema(self):
        return self.resultados.conflicto_o_problema

    def preidentificaciones(self):
        return self.resultados.preidentificaciones
