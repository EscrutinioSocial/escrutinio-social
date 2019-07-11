from functools import partial
from datetime import timedelta
from urllib.parse import quote_plus
from django.utils import timezone
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


class Attachment(models.Model):
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
    mesa = models.ForeignKey('elecciones.Mesa', null=True, related_name='attachments', on_delete=models.CASCADE)
    taken = models.DateTimeField(null=True)
    problema = models.CharField(max_length=100, null=True, blank=True, choices=PROBLEMAS)

    def save(self, *args, **kwargs):
        """
        Actualiza el hash de la imágen original asociada antes de guardar.
        Notar que esto puede puede producir una excepción si la imágen (el digest)
        ya es conocido en el sistema
        """
        if self.foto:
            self.foto.file.open()
            self.foto_digest = hash_file(self.foto.file)
        super().save(*args, **kwargs)

    @classmethod
    def sin_asignar(cls, wait=2):
        """
        Devuelve un conjunto de Attachments que no tienen problemas
        ni mesas asociados y no ha sido asignado para clasificar en los últimos
        ``wait`` minutos
        """
        desde = timezone.now() - timedelta(minutes=wait)
        return cls.objects.filter(
            Q(problema__isnull=True, mesa__isnull=True),
            Q(taken__isnull=True) | Q(taken__lt=desde)
        )

    def __str__(self):
        return f'{self.foto} ({self.mimetype})'


@receiver(post_save, sender=Attachment)
def asignar_orden_de_carga(sender, instance=None, created=False, **kwargs):
    """
    Cuando se clasifica el attachment, a la mesa asociada se le asigna el orden de carga
    que corresponda actualmente al circuito
    """
    if instance.mesa and not instance.mesa.cargas.exists():
        mesa = instance.mesa
        mesa.orden_de_carga = mesa.circuito.proximo_orden_de_carga()
        mesa.save(update_fields=['orden_de_carga'])
