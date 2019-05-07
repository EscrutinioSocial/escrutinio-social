from django.db import models
from model_utils import Choices
from model_utils.models import TimeStampedModel


class Problema(TimeStampedModel):

    PROBLEMAS = Choices(
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
    reportado_por = models.ForeignKey('fiscales.Fiscal')
    descripcion = models.TextField(null=True, blank=True)
    estado = models.CharField(max_length=100, null=True, blank=True, choices=ESTADOS)
    resuelto_por = models.ForeignKey('auth.User', null=True)