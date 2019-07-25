from django.db import models
from .models import (Circuito, Categoria)

class PrioridadScheduling(models.Model):
    """
    Representa una prioridad distinta de la standard para 
    una determinada categoria o circuito
    """
    circuito = models.ForeignKey(Circuito, null=True, related_name="prioridades", on_delete=models.CASCADE)
    categoria = models.ForeignKey(Categoria, null=True, related_name="prioridades", on_delete=models.CASCADE)
    # desde / hasta: pueden ser 0, no pueden ser null ni negativos
    desde = models.PositiveIntegerField(null=False)
    hasta = models.PositiveIntegerField(null=False)
    # prioridad: no pueden ser null ni negativo, en discusion si puede ser 0, por ahora se permite
    prioridad = models.PositiveIntegerField(null=False)


class RangosDeProporcionesSeSolapanError(Exception):
    pass


class RegistroDePrioridad():
    """
    Representa la correspondencia de una prioridad con un rango de proporciones.
    """

    def __init__(self, desde, hasta, prioridad):
        self.desde = desde
        self.hasta = hasta
        self.prioridad = prioridad

    def aplica(self, proporcion):
        return self.desde <= proporcion and (self.hasta==100 or self.hasta > proporcion)

    def es_compatible_con(self, otro):
        return self.hasta <= otro.desde or otro.hasta <= self.desde

    def __str__(self):
        return F"De {self.desde}% a {self.hasta}% corresponde prioridad {self.prioridad}"


class MapaPrioridades():
    """
    Representa un mapa entre proporción y prioridad, armado a partir de un conjunto 
    de instancias de RegistroDePrioridad.
    P.ej. desde 4% a 8%, corresponde prioridad 10.
    """

    def __init__(self):
        self.registros = []

    def agregarRegistro(self, registro):
        registro_incompatible = next((reg for reg in self.registros if not reg.es_compatible_con(registro)), None)
        if registro_incompatible:
            raise RangosDeProporcionesSeSolapanError(
                F"Rangos se solapan entre <{registro}> y <{registro_incompatible}>")
        self.registros.append(registro)

    def registro_que_aplica(self, proporcion):
        return next((reg for reg in self.registros if reg.aplica(proporcion)), None)

    def valor_para(self, proporcion):
        registro = self.registro_que_aplica(proporcion)
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
    
    def valor_para(self, proporcion):
        valor_principal = self.principal.valor_para(proporcion)
        # no uso el "or" para respetar que el valor_principal podría ser 0, que es falsy
        return valor_principal if valor_principal is not None else self.default.valor_para(proporcion)


class MapaPrioridadesProducto():
    """
    Un MapaPrioridades compuesto, que devuelve el producto de los valores que entregan sus dos factores.
    Devuelve None si al menos un factor devuelve None.
    """
    def __init__(self, factor_1, factor_2):
        self.factor_1 = factor_1
        self.factor_2 = factor_2
    
    def valor_para(self, proporcion):
        valores = [self.factor_1.valor_para(proporcion), self.factor_2.valor_para(proporcion)]
        if any(valor is None for valor in valores):
            return None
        return valores[0] * valores[1]


def prioridades_categoria_standard():
    pass
