from django.conf import settings
from functools import partial
from datetime import timedelta
from urllib.parse import quote_plus
from django.utils import timezone
from model_utils import Choices
from model_utils.fields import StatusField
from model_utils.models import TimeStampedModel
from django.db.models import Count, Value
from django.db.models.functions import Coalesce
from django.db.models import Q
from django.db import models
import hashlib
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
    STATUS = Choices(
        ('sin_identificar', 'sin identificar'),
        'identificada',
        'problema',
    )
    status = StatusField(default=STATUS.sin_identificar)
    mesa = models.ForeignKey(
        'elecciones.Mesa', related_name='attachments', null=True, blank=True, on_delete=models.SET_NULL
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

    # Identificación representativa del estado actual.
    identificacion_testigo = models.ForeignKey(
        'Identificacion', related_name='es_testigo',
        null=True, blank=True, on_delete=models.SET_NULL
    )

    def take(self):
        self.taken = timezone.now()
        self.save(update_fields=['taken'])

    def release(self):
        """
        Libera una mesa, es lo contrario de take().
        """
        self.taken = None
        self.save(update_fields=['taken'])

    def save(self, *args, **kwargs):
        """
        Actualiza el hash de la imágen original asociada antes de guardar.
        Notar que esto puede puede producir una excepción si la imágen (el digest)
        ya es conocido en el sistema.
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
    def sin_identificar(cls, fiscal_a_excluir=None):
        """
        Devuelve un conjunto de Attachments que no tienen
        identificación consolidada y no han sido asignados
        para clasificar en los últimos ``settings.ATTACHMENT_TAKE_WAIT_TIME`` minutos.

        Se excluyen attachments que ya hayan sido clasificados por `fiscal_a_excluir`
        """
        wait = settings.ATTACHMENT_TAKE_WAIT_TIME
        return cls.sin_identificar_con_timeout(wait=wait, fiscal_a_excluir=fiscal_a_excluir)

    @classmethod
    def sin_identificar_con_timeout(cls, wait=2, fiscal_a_excluir=None):
        """
        Es la implementación de sin_identificar() que se expone sólo para poder
        testear más fácilmente
        """
        desde = timezone.now() - timedelta(minutes=wait)
        qs = cls.objects.filter(
            Q(taken__isnull=True) | Q(taken__lt=desde),
            status='sin_identificar',
        )
        if fiscal_a_excluir:
            qs = qs.exclude(identificaciones__fiscal=fiscal_a_excluir)
        return qs

    def status_count(self, estado):
        """
        A partir del conjunto de identificaciones del attachment
        que tienen el estado parámetro devuelve una lista de tuplas
        (mesa_id, cantidad, cantidad que viene de csv).
        Sólo cuenta las no invalidadas.

        Cuando status == 'problema' el id de mesa es None

        Por ejemplo (cuando estado == 'identificada'):
            [
                (3, 2, 0),
                (4, 1, 1),
            ]

        Hay 2 identificaciones para la mesa id==3 y 1 para la id==4, pero ésa 
        tiene una identificación por CSV.
        """

        qs = self.identificaciones.filter(status=estado, invalidada=False)
        cuantos_csv = Count('source', filter=Q(source=Identificacion.SOURCES.csv))
        result = []
        query = qs.values('mesa', 'status').annotate(
                mesa_o_0=Coalesce('mesa', Value(0))     # Esto es para facilitar el testing.
            ).annotate(
                total=Count('status')
            ).annotate(
                cuantos_csv=cuantos_csv
            )
        for item in query:
            result.append(
                (item['mesa_o_0'], item['total'], item['cuantos_csv'])
            )
        return result

    def __str__(self):
        return f'{self.foto} ({self.mimetype})'


class Identificacion(TimeStampedModel):
    """
    Es el modelo que guarda clasificaciones de actas para asociarlas a mesas
    """
    STATUS = Choices(
        'identificada',
        'problema'
    )
    status = StatusField(choices_name='STATUS')

    SOURCES = Choices('web', 'csv', 'telegram')
    source = StatusField(choices_name='SOURCES', default=SOURCES.web)

    fiscal = models.ForeignKey(
        'fiscales.Fiscal', null=True, blank=True, on_delete=models.SET_NULL
    )
    mesa = models.ForeignKey(
        'elecciones.Mesa',  null=True, blank=True, on_delete=models.SET_NULL
    )
    attachment = models.ForeignKey(
        Attachment, related_name='identificaciones', on_delete=models.CASCADE
    )
    procesada = models.BooleanField(default=False)
    invalidada = models.BooleanField(default=False)

    def __str__(self):
        return f'id: {self.id} - {self.status} - {self.mesa} - {self.fiscal} - procesada: {self.procesada} - invalidada: {self.invalidada}'

    def invalidar(self):
        self.invalidada = True
        self.save(update_fields=['invalidada'])
