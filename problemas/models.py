from django.db import models
from model_utils import Choices
from model_utils.models import TimeStampedModel


class Problema(TimeStampedModel):

    PROBLEMAS = Choices(
        'Error de carga en Gobernador',
        'Error de carga en Legisladores',
        'Error de carga en Intendente'
        'Foto/s no válidas',
        'Total incorrecto',
        'Otro'
    )
    ESTADOS = Choices(
        'pendiente',
        'en curso',
        'resuelto',
    )
    problema = models.CharField(max_length=100, null=True, blank=True, choices=PROBLEMAS)
    mesa = models.ForeignKey('elecciones.Mesa', related_name='problemas', on_delete=models.CASCADE)
    reportado_por = models.ForeignKey('fiscales.Fiscal', on_delete=models.CASCADE)
    descripcion = models.TextField(null=True, blank=True)
    estado = models.CharField(max_length=100, null=True, blank=True, choices=ESTADOS)
    resuelto_por = models.ForeignKey(
        'auth.User', null=True, on_delete=models.SET_NULL
    )