from django.db import models
from django.urls import reverse
from model_utils import Choices

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class DatoDeContacto(models.Model):
    """Modelo generérico para guardar datos de contacto de personas o medios

    Ejemplo de uso::

        from django.contrib.contenttypes.fields import GenericRelation

        class Cliente(models.Model):
            datos_de_contacto = GenericRelation(
                'contacto.DatoDeContacto',
                related_query_name='clientes'
            )
            ...
    """

    TIPOS = Choices(
        'teléfono', 'email', 'web', 'twitter', 'facebook',
        'instagram', 'youtube', 'skype'
    )

    tipo = models.CharField(choices=TIPOS, max_length=20)
    valor = models.CharField(max_length=100)
    # generic relation
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = (('tipo', 'valor', 'content_type', 'object_id'),)

    def __str__(self):
        return f'{self.tipo}: {self.valor}'
