from django.db import models, transaction, connection
from django.conf import settings
from django.db.models import Q, F, ExpressionWrapper, Case, When
from constance import config

from elecciones.models import (Distrito, Seccion, Categoria, MesaCategoria)
from adjuntos.models import Attachment


class ColaCargasPendientes(models.Model):
    """
    Modelo que mantiene los trabajos de carga de votos pendientes a hacer.
    """
    mesa_categoria = models.ForeignKey(MesaCategoria, on_delete=models.CASCADE, null=True)
    attachment = models.ForeignKey(Attachment, on_delete=models.CASCADE, null=True)
    # Este campo lo calcula el encolador.
    orden = models.PositiveIntegerField(db_index=True)
    numero_carga = models.PositiveIntegerField(default=1)
    # Denormalización para facilitar el cálculo de afinidad.
    distrito = models.ForeignKey(Distrito, null=True, blank=True, on_delete=models.SET_NULL)
    
    class Meta:
        unique_together = [
            ['mesa_categoria', 'numero_carga'],
            ['attachment', 'numero_carga']
        ]
        verbose_name = 'Cola de Identificaciones y Cargas pendientes'
        verbose_name_plural = 'Cola de Identificaciones y Cargas pendientes'

    @classmethod
    def largo_cola(cls):
        return cls.objects.count()

    @classmethod
    def siguiente_tarea(cls, fiscal=None):
        """
        Obtiene la siguiente tarea de la cola.
        El fiscal parámetro indica que deben excluirse mesascat que ya hayan sido cargadas por él.
        Debe invocarse dentro de una transacción.
        """
        excluir = (Q(mesa_categoria__cargas__fiscal=fiscal) |
                   Q(attachment__identificaciones__fiscal=fiscal)) if fiscal else Q()
        mesa_categoria , attachment = None , None
        
        query = cls.objects.select_for_update(skip_locked=True).exclude(excluir)
        
        # Se privilegia a las tareas del distrito en las que viene trabajando el fiscal.
        if fiscal and fiscal.distrito_afin:
            orden_afin = Case(
                When(distrito=fiscal.distrito_afin,
                     then=F('orden')-config.BONUS_AFINIDAD_GEOGRAFICA
                ),
                default=F('orden'),
                output_field=models.IntegerField()
            )
            query = query.order_by(orden_afin)
        else:
            query = query.order_by('orden')
            
        item = query.first()
        if item:
            mesa_categoria = item.mesa_categoria
            attachment = item.attachment
            item.delete()

        return (mesa_categoria, attachment)

    @classmethod
    def vaciar(cls):
        #cls.objects.all().delete()
        with connection.cursor() as cursor:
            cursor.execute(f'TRUNCATE TABLE {cls._meta.db_table}')

    @classmethod
    def debug(cls, fiscal):
        return cls.objects.exclude(
            Q(mesa_categoria__cargas__fiscal=fiscal) |
            Q(attachment__identificaciones__fiscal=fiscal)
        ).order_by('orden')

    def __str__(self):
        return f'({self.orden}) <{self.mesa_categoria}, {self.attachment}>'


class PrioridadScheduling(models.Model):
    """
    Representa una prioridad distinta de la standard para
    una determinada categoria o seccion.
    Una prioridad aplica o no, dependiendo de la proporcion de las MesaCategoria que tengan foto asociada,
    y el orden de llegada de la foto de cada MesaCategoria.

    Se pueden establecer dos criterios para que esta prioridad aplique,
    - desde / hasta proporcion de MesaCategoria con foto.
    - hasta cantidad, de acuerdo al orden de llegada de la foto.
      El uso de este segundo criterio es optativo; hasta_cantidad acepta null/None.
    Se considera la disyuncion entre estos criterios.
    """
    seccion = models.ForeignKey(Seccion, null=True, related_name="prioridades", on_delete=models.CASCADE)
    categoria = models.ForeignKey(Categoria, null=True, related_name="prioridades", on_delete=models.CASCADE)
    # desde_proporcion / hasta_proporcion: pueden ser 0, no pueden ser null ni negativos
    desde_proporcion = models.PositiveIntegerField(null=False)
    hasta_proporcion = models.PositiveIntegerField(null=False)
    # prioridad: no puede ser negativo, en discusion si puede ser 0, por ahora se permite.
    # Se permite null, para definir una prioridad solamente para establecer hasta_cantidad
    prioridad = models.PositiveIntegerField(null=True)
    # hasta_cantidad: puede ser null
    hasta_cantidad = models.PositiveIntegerField(null=True)

    def como_registro_prioridad(self):
        return RegistroDePrioridad(self.desde_proporcion, self.hasta_proporcion, self.prioridad, self.hasta_cantidad)

    @classmethod
    def mapa_prioridades(cls, query_set):
        """
        Crea un MapaPrioridades a partir de QuerySet de ProridadScheduling.
        """
        mapa = MapaPrioridades()
        for prioridad_scheduling in query_set:
            mapa.agregar_registro(prioridad_scheduling.como_registro_prioridad())
        return mapa


# funciones para mantener las instancias de PrioridadScheduling
# **OJO**: se limitan a lo necesario para la UI de Categoria y Seccion tal cual se la está implementando
# Carlos Lombardi, 2019.07.31
def registrar_prioridad_categoria(categoria):
    # se podría optimizar para modificar el registro existente, pero prefiero
    # una implementación más sencilla: si había un registro lo borro, si hace falta que haya lo agrego

    # paso 1: si había una PrioridadScheduling para esta Categoria, la borro
    prioridad_scheduling_actual = PrioridadScheduling.objects.filter(categoria=categoria).first()
    if prioridad_scheduling_actual:
        prioridad_scheduling_actual.delete()

    # paso 2: si la categoría tiene seteada una prioridad, creo una nueva PrioridadScheduling para ella
    #         OJO - acá se confía en que las prioridades no pueden ser 0
    if categoria.prioridad:
        nueva_prioridad_scheduling = PrioridadScheduling(
            categoria=categoria, desde_proporcion=0, hasta_proporcion=100, prioridad=categoria.prioridad)
        nueva_prioridad_scheduling.save()


def registrar_prioridades_seccion(seccion):
    # paso 1: borro las prioridades que haya registradas para esta sección
    for prioridad_scheduling_actual in PrioridadScheduling.objects.filter(seccion=seccion):
        prioridad_scheduling_actual.delete()

    # paso 2: agrego las prioridades para las que haya valores seteados en la sección
    #         OJO - acá se confía en que ni prioridades ni cantidades mínimas pueden ser 0

    # hasta 2%
    if seccion.prioridad_hasta_2 or seccion.cantidad_minima_prioridad_hasta_2:
        nueva_prioridad_scheduling = PrioridadScheduling(
            seccion=seccion, desde_proporcion=0, hasta_proporcion=2,
            prioridad=seccion.prioridad_hasta_2, hasta_cantidad=seccion.cantidad_minima_prioridad_hasta_2)
        nueva_prioridad_scheduling.save()

    # de 2% a 10%
    if seccion.prioridad_2_a_10:
        nueva_prioridad_scheduling = PrioridadScheduling(
            seccion=seccion, desde_proporcion=2, hasta_proporcion=10, prioridad=seccion.prioridad_2_a_10)
        nueva_prioridad_scheduling.save()

    # de 10% a 100%
    if seccion.prioridad_10_a_100:
        nueva_prioridad_scheduling = PrioridadScheduling(
            seccion=seccion, desde_proporcion=10, hasta_proporcion=100, prioridad=seccion.prioridad_10_a_100)
        nueva_prioridad_scheduling.save()


class RangosDeProporcionesSeSolapanError(Exception):
    pass


class RegistroDePrioridad():
    """
    Representa la correspondencia de una prioridad con un rango de proporciones.
    """

    def __init__(self, desde_proporcion, hasta_proporcion, prioridad, hasta_cantidad=None):
        self.desde_proporcion = desde_proporcion
        self.hasta_proporcion = hasta_proporcion
        self.prioridad = prioridad
        self.hasta_cantidad = hasta_cantidad

    def aplica(self, proporcion, orden_de_llegada):
        return (self.desde_proporcion <= proporcion and (self.hasta_proporcion == 100 or self.hasta_proporcion > proporcion)) \
            or (self.hasta_cantidad and orden_de_llegada <= self.hasta_cantidad)

    def es_compatible_con(self, otro):
        return self.hasta_proporcion <= otro.desde_proporcion or otro.hasta_proporcion <= self.desde_proporcion

    def __str__(self):
        return F"De {self.desde_proporcion}% a {self.hasta_proporcion}% corresponde prioridad {self.prioridad}"


class MapaPrioridades():
    """
    Representa un mapa entre proporción y prioridad, armado a partir de un conjunto
    de instancias de RegistroDePrioridad.
    P.ej. desde_proporcion 4% a 8%, corresponde prioridad 10.
    """

    def __init__(self):
        self.registros = []

    def agregar_registro(self, registro):
        registro_incompatible = next(
            (reg for reg in self.registros if not reg.es_compatible_con(registro)), None)
        if registro_incompatible:
            raise RangosDeProporcionesSeSolapanError(
                F"Rangos se solapan entre <{registro}> y <{registro_incompatible}>")
        self.registros.append(registro)

    def registros_ordenados(self):
        registros_ordenados = list(self.registros)
        registros_ordenados.sort(key=lambda reg: reg.desde_proporcion)
        return registros_ordenados

    def registro_que_aplica(self, proporcion, orden_de_llegada):
        return next((reg for reg in self.registros_ordenados() if reg.aplica(proporcion, orden_de_llegada)), None)

    def valor_para(self, proporcion, orden_de_llegada):
        registro = self.registro_que_aplica(proporcion, orden_de_llegada)
        if registro:
            return registro.prioridad
        return None


class MapaPrioridadesConDefault():
    """
    Un MapaPrioridades compuesto, tiene un principal y un default.
    Para una dada proporción, si el principal no tiene valor, entonces delega en el default.
    """

    def __init__(self, principal, default):
        self.principal = principal
        self.default = default

    def valor_para_viejo(self, proporcion, orden_de_llegada):
        valor_principal = self.principal.valor_para(proporcion, orden_de_llegada)
        # no uso el "or" para respetar que el valor_principal podría ser 0, que es falsy
        return valor_principal if valor_principal is not None else self.default.valor_para(proporcion, orden_de_llegada)

    def valor_para(self, proporcion, orden_de_llegada):
        registro_que_aplica_principal = self.principal.registro_que_aplica(proporcion, orden_de_llegada)
        # si ningun registro en el mapa principal aplica, define el default
        if not registro_que_aplica_principal:
            return self.default.valor_para(proporcion, orden_de_llegada)
        # tengo un registro en el mapa principal. Si define prioridad, la uso
        prioridad_principal = registro_que_aplica_principal.prioridad
        if prioridad_principal is not None:
            return prioridad_principal
        # si se llegó hasta acá, es que hay un registro en el mapa principal, pero que no define prioridad.
        # esto puede pasar si el registro se creó solamente para definir hasta_cantidad
        # en tal caso, usamos el valor del registro default **para el desde_proporcion** del registro principal que aplica
        return self.default.valor_para(registro_que_aplica_principal.desde_proporcion, orden_de_llegada)


class MapaPrioridadesProducto():
    """
    Un MapaPrioridades compuesto, que devuelve el producto de los valores que entregan sus dos factores.
    Devuelve None si al menos un factor devuelve None.
    """

    def __init__(self, factor_1, factor_2):
        self.factor_1 = factor_1
        self.factor_2 = factor_2

    def valor_para(self, proporcion, orden_de_llegada):
        valores = [self.factor_1.valor_para(proporcion, orden_de_llegada),
                   self.factor_2.valor_para(proporcion, orden_de_llegada)]
        if any(valor is None for valor in valores):
            return None
        return valores[0] * valores[1]


def registro_prioridad_desde_estructura(estructura):
    """
    Crea un RegistroPrioridad a partir de una estructura
    {'desde_proporcion': nro, 'hasta_proporcion': nro, 'prioridad': nro, 'hasta_cantidad': nro}
    donde el hasta_cantidad es optativo
    """
    regi = RegistroDePrioridad(estructura['desde_proporcion'], estructura['hasta_proporcion'], estructura['prioridad'])
    if 'hasta_cantidad' in estructura:
        regi.hasta_cantidad = estructura['hasta_cantidad']
    return regi


def mapa_prioridades_desde_setting(setting):
    """
    Crea un MapaPrioridades a partir de una lista [{'desde_proporcion': nro, 'hasta_proporcion': nro, 'prioridad': nro}]
    que es el formato que tiene la especificación de prioridades en los settings.
    """
    mapa = MapaPrioridades()
    for estructura in setting:
        mapa.agregar_registro(registro_prioridad_desde_estructura(estructura))
    return mapa


def mapa_prioridades_para_seccion(seccion):
    """
    Crea y devuelve el MapaPrioridades que corresponde a una Seccion, de acuerdo a las PrioridadScheduling
    que hubiera definidas.
    """
    return PrioridadScheduling.mapa_prioridades(PrioridadScheduling.objects.filter(seccion=seccion, categoria=None))


def mapa_prioridades_default_categoria():
    return mapa_prioridades_desde_setting(settings.PRIORIDADES_STANDARD_CATEGORIA)


def mapa_prioridades_default_seccion():
    return mapa_prioridades_desde_setting(settings.PRIORIDADES_STANDARD_SECCION)


def mapa_prioridades_para_categoria(categoria):
    """
    Crea y devuelve el MapaPrioridades que corresponde a una Categoria, de acuerdo a las PrioridadScheduling
    que hubiera definidas.
    """
    return PrioridadScheduling.mapa_prioridades(PrioridadScheduling.objects.filter(categoria=categoria, seccion=None))


def mapa_prioridades_para_mesa_categoria(mesa_categoria):
    """
    Crea y devuelve el MapaPrioridades que corresponde a una MesaCategoria, de acuerdo a su categoria y a su seccion
    """
    # obtengo los mapas para seccion y categoria, con default a lo que sale de los settings
    mapa_especifico_seccion = mapa_prioridades_para_seccion(mesa_categoria.mesa.lugar_votacion.circuito.seccion)
    mapa_seccion = MapaPrioridadesConDefault(mapa_especifico_seccion, mapa_prioridades_default_seccion())

    mapa_especifico_categoria = mapa_prioridades_para_categoria(mesa_categoria.categoria)
    mapa_categoria = MapaPrioridadesConDefault(mapa_especifico_categoria, mapa_prioridades_default_categoria())

    # a la MesaCategoria le corresponde el __producto__ entre seccion y categoria
    return MapaPrioridadesProducto(mapa_seccion, mapa_categoria)
