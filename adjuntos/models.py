from django.conf import settings
from functools import partial
from datetime import timedelta
from urllib.parse import quote_plus
from django.utils import timezone
from model_utils import Choices
from model_utils.fields import StatusField
from model_utils.models import TimeStampedModel
from django.db.models import (
    OuterRef, Exists, Count
)

from django.db.models import Q
from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_save
import hashlib
from model_utils import Choices
from versatileimagefield.fields import VersatileImageField


def hash_file(file, block_size=65536):
    """
    Dado un objeto file-like (en modo binario),
    devuelve un hash digest único de 128 digitos hexadecimales

    Utiliza el algoritmo de hashing
    `blake2 <https://en.wikipedia.org/wiki/BLAKE_(hash_function)>`_
    ::

        >>> hash_file(open('messi.jpg', 'rb'))
        '90554e1d519e0fc665fab042d7499a1bc9c191f2a13b0b2c369753dcb23b181866cb116007fc37a445421270e04912a46dbfb6a325cf27a2603eed45fc1d41b1'

    """
    hasher = hashlib.blake2b()
    for buf in iter(partial(file.read, block_size), b''):
        hasher.update(buf)
    return hasher.hexdigest()


class Email(models.Model):
    """
    Almacena la información de emails que entran al sistema y contienen attachments
    La persistencia de estos objetos no es estrictamente necesaria.

    Ver :py:mod:`elecciones.management.commands.importar_actas`
    """
    date = models.CharField(max_length=100)
    from_address = models.CharField(max_length=200)
    body = models.TextField()
    title = models.CharField(max_length=150)
    uid = models.PositiveIntegerField()
    message_id = models.CharField(max_length=300)

    @classmethod
    def from_mail_object(cls, mail):
        return Email.objects.create(
            body=mail.body,
            title=mail.title,
            date=mail.date,
            from_address=mail.from_addr,
            uid=mail.uid,
            message_id=mail.message_id
        )

    def __str__(self):
        return f'from:{self.from_address} «{self.title}»'

    @property
    def gmail_url(self):
        mid = quote_plus(f':{self.message_id}')
        return f'https://mail.google.com/mail/u/0/#search/rfc822msgid{mid}'


class Attachment(TimeStampedModel):
    """
    Guarda las fotos de ACTAS y otros documentos fuente desde los cuales se cargan los datos.
    Están asociados a una imágen que a su vez puede tener una versión editada.

    Los attachments están asociados a mesas una vez que se clasifican.

    No pueden existir dos instancias de este modelo con la misma foto, dado que
    el atributo digest es único.
    """

    PROBLEMAS = Choices(
        'no es una foto válida',
        'no se entiende',
        # 'foto rotada',
    )

    email = models.ForeignKey('Email', null=True, on_delete=models.SET_NULL)
    mimetype = models.CharField(max_length=100, null=True)
    foto = VersatileImageField(upload_to='attachments/',
        null=True, blank=True,
        width_field='width',
        height_field='height'
    )
    foto_edited = VersatileImageField(upload_to='attachments/edited',
        null=True, blank=True,
        width_field='width',
        height_field='height'
    )
    foto_digest = models.CharField(max_length=128, unique=True)

    height = models.PositiveIntegerField(
        'Image Height',
        blank=True,
        null=True
    )
    width = models.PositiveIntegerField(
        'Image Width',
        blank=True,
        null=True
    )
    taken = models.DateTimeField(null=True)
    problema = models.CharField(max_length=100, null=True, blank=True, choices=PROBLEMAS)

    def save(self, *args, **kwargs):
        """
        Actualiza el hash de la imágen original asociada antes de guardar.
        Notar que esto puede puede producir una excepción si la imágen (el digest)
        ya es conocido en el sistema
        """
        if self.foto and not self.foto_digest:
            # FIXME
            # sólo se calcula el digest cuando no hay uno previo.
            # esto impide recalcular el digest si eventualmente cambia
            # la imagen por algun motivo
            # Mejor seria verificar con un MonitorField si la foto cambió
            # y sólo en ese caso actualizar el hash.
            self.foto.file.open()
            self.foto_digest = hash_file(self.foto.file)
        super().save(*args, **kwargs)


    @classmethod
    def sin_identificar(cls, wait=2, fiscal=None):
        """
        Devuelve un conjunto de Attachments que no tienen problemas
        ni identificacion consolidada y no ha sido asignado
        para clasificar en los últimos ``wait`` minutos

        Se excluyen attachments que ya hayan sido clasificados por `fiscal`
        """
        desde = timezone.now() - timedelta(minutes=wait)
        qs = cls.objects.filter(
            Q(problema__isnull=True),
            Q(taken__isnull=True) | Q(taken__lt=desde)
        ).annotate(
            consolidada=Exists(
                Identificacion.objects.filter(
                    Q(attachment__id=OuterRef('id')),
                    Q(consolidada=True)
                )
            )
        ).filter(
            consolidada=False
        )
        if fiscal:
            qs = qs.exclude(identificacion__fiscal=fiscal)
        return qs


    def __str__(self):
        return f'{self.foto} ({self.mimetype})'


class Identificacion(TimeStampedModel):
    """
    Es el modelo que guarda clasificaciones de actas para asociarlas a mesas
    """
    STATUS = Choices(
        'identificada',
        'spam',
        'invalida'
    )
    status = StatusField()

    consolidada = models.BooleanField(
        default=False,
        help_text=(
            'una identificacion consolidada es aquella '
            'que se considera representativa y determina '
            'el estado del attachment'
        )
    )
    fiscal = models.ForeignKey(
        'fiscales.Fiscal', null=True, blank=True, on_delete=models.SET_NULL
    )
    mesa = models.ForeignKey(
        'elecciones.Mesa',  null=True, blank=True, on_delete=models.CASCADE
    )
    attachment = models.ForeignKey(
        Attachment, related_name='identificaciones', on_delete=models.CASCADE
    )

    @classmethod
    def status_count(cls, attachment, exclude=None):
        """
        a partir del conjunto de identificaciones del attachment
        se devuelve un diccionario con los cantidades para
        cada grupo (mesa_id, status)
        Por ejmplo:
            {
                (None, 'spam'): 2,
                (None, 'invalida'): 1,
                (1, 'identificada'): 1,
                (2, 'identificada'): 1,
            }

        2 lo identificaron como spam, 1 como inválida,
        1 a la mesa id=1, y otro a la mesa id=2
        """

        qs = cls.objects.filter(attachment=attachment)
        if exclude:
            # en caso de que se pase ID, se excluye
            # este objeto, de manera de poder
            qs = exclude(id=exclude)
        result = {}
        for item in qs.values('mesa', 'status').annotate(total=Count('status')):
            result[(item['mesa'], item['status'])] = item['total']
        return result

    def save(self, *args, **kwargs):
        if self.attachment:
            same_status_count = Identificacion.status_count(
                self.attachment, self.id
            ).get((self.mesa, self.status))

            if same_status_count and same_status_count + 1 >= settings.MIN_COINCIDENCIAS_IDENTIFICACION:
                self.consolidada = True
        super().save(*args, **kwargs)


@receiver(post_save, sender=Identificacion)
def asignar_orden_de_carga(sender, instance=None, created=False, **kwargs):
    """
    Cuando se guarda una identificacion que consolida,
    a la mesa asociada se le asigna el orden de carga
    que corresponda actualmente al circuito
    """
    if (
        instance.status == Identificacion.STATUS.identificada and
        instance.consolidada and
        not instance.mesa.carga_set.exists()
    ):
        mesa = instance.mesa
        mesa.orden_de_carga = mesa.lugar_votacion.circuito.proximo_orden_de_carga()
        mesa.save(update_fields=['orden_de_carga'])
