from functools import partial
from datetime import timedelta
from urllib.parse import quote_plus

from django.conf import settings
from constance import config
from django.utils import timezone
from django.db.models import Count, Value, F
from django.db.models.functions import Coalesce
from django.db.models import Q
from django.db import models, transaction
from model_utils import Choices
from model_utils.fields import StatusField
from model_utils.models import TimeStampedModel
import structlog
import hashlib
from versatileimagefield.fields import VersatileImageField


logger = structlog.get_logger(__name__)


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


class AttachmentQuerySet(models.QuerySet):

    def sin_identificar(self, fiscal_a_excluir=None, for_update=True):
        """
        Devuelve un conjunto de Attachments que no tienen
        identificación consolidada.

        Se excluyen attachments que ya hayan sido clasificados por `fiscal_a_excluir`
        """
        qs = self.select_for_update(skip_locked=True) if for_update else self
        qs = qs.filter(
            status='sin_identificar',
        )
        if fiscal_a_excluir:
            qs = qs.exclude(identificaciones__fiscal=fiscal_a_excluir)
        return qs

    def redondear_cant_fiscales_asignados_y_de_asignaciones(self):
        """
        Redondea la cantidad de fiscales asignados y de asignaciones a múltiplos de
        ``settings.MIN_COINCIDENCIAS_IDENTIFICACION`` para que al asignar mesas
        no se pospongan indefinidamente mesas que fueron entregadas ya a algún
        fiscal.
        """
        return self.annotate(
            cant_fiscales_asignados_redondeados=F(
                'cant_fiscales_asignados') / settings.MIN_COINCIDENCIAS_IDENTIFICACION,
            cant_asignaciones_realizadas_redondeadas=F(
                'cant_asignaciones_realizadas') / 
                (config.MULTIPLICADOR_CANT_ASIGNACIONES_REALIZADAS * settings.MIN_COINCIDENCIAS_IDENTIFICACION),
        )

    def priorizadas(self):
        """
        Ordena por cantidad de fiscales trabajando en el momento,
        luego por cantidad de personas que alguna vez trabajaron,
        y por último por orden de llegada.
        """
        return self.redondear_cant_fiscales_asignados_y_de_asignaciones().order_by(
            'cant_fiscales_asignados_redondeados',
            'cant_asignaciones_realizadas_redondeadas',
            'id'
        )


class Attachment(TimeStampedModel):
    """
    Guarda las fotos de ACTAS y otros documentos fuente desde los cuales se cargan los datos.
    Están asociados a una imágen que a su vez puede tener una versión editada.

    Los attachments están asociados a mesas una vez que se clasifican.

    No pueden existir dos instancias de este modelo con la misma foto, dado que
    el atributo digest es único.
    """
    objects = AttachmentQuerySet.as_manager()

    STATUS = Choices(
        ('sin_identificar', 'sin identificar'),
        'identificada',
        'problema',
    )
    status = StatusField(default=STATUS.sin_identificar)
    mesa = models.ForeignKey(
        'elecciones.Mesa', related_name='attachments', null=True, blank=True, on_delete=models.SET_NULL
    )
    email = models.ForeignKey('Email', null=True, blank=True, on_delete=models.SET_NULL)
    mimetype = models.CharField(max_length=100, null=True)
    foto = VersatileImageField(
        upload_to='attachments/',
        null=True,
        blank=True,
        width_field='width',
        height_field='height'
    )
    foto_edited = VersatileImageField(
        upload_to='attachments/edited',
        null=True,
        blank=True,
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

    subido_por = models.ForeignKey(
        'fiscales.Fiscal', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='attachments_subidos'
    )

    # Identificación representativa del estado actual.
    identificacion_testigo = models.ForeignKey(
        'Identificacion', related_name='es_testigo',
        null=True, blank=True, on_delete=models.SET_NULL
    )

    # Información parcial de identificación que se completa cuando se
    # sube el attachment y sirve para precomplentar parte de la identificación.
    pre_identificacion = models.ForeignKey(
        'PreIdentificacion', related_name='attachment',
        null=True, blank=True, on_delete=models.SET_NULL
    )

    # Registra a cuántos fiscales se les entregó la mesa para que trabajen en ella y aún no la
    # devolvieron.
    cant_fiscales_asignados = models.PositiveIntegerField(
        default=0,
        blank=False,
        null=False
    )

    # Este otro contador, en cambio, registra cuántas veces fue entregado un attachment
    # a algún fiscal. Su objetivo es desempatar y hacer que en caso de que todos los demás
    # parámetros de prioridad sea iguales (por ejemplo, muchos attachs sin identificar, de una
    # misma ubicación prioritaria), no se tome siempre a la de menor id, introduciendo cierta
    # variabilidad y evitando la repetición de trabajo.
    cant_asignaciones_realizadas =  models.PositiveIntegerField(
        default=0,
        blank=False,
        null=False
    )

    def asignar_a_fiscal(self):
        self.cant_fiscales_asignados += 1
        self.cant_asignaciones_realizadas += 1
        self.save(update_fields=['cant_fiscales_asignados', 'cant_asignaciones_realizadas'])
        logger.info('Attachment asignado', id=self.id)

    def desasignar_a_fiscal(self):
        # Si por error alguien hizo un submit de más, no es un problema, por eso se redondea a cero.
        self.cant_fiscales_asignados = max(0, self.cant_fiscales_asignados - 1)
        self.save(update_fields=['cant_fiscales_asignados'])
        logger.info('Attachment desasignado', id=self.id)

    def crear_pre_identificacion_si_corresponde(self):
        """
        Le asocia al attachment una PreIdentificacion con los datos del fiscal que la subió
        si no hay una previa.
        """
        if self.pre_identificacion:
            return

        # Si no tengo quién la subió tampoco lo puedo hacer.
        if not self.subido_por:
            return

        self.pre_identificacion = PreIdentificacion.objects.create(
            fiscal=self.subido_por,
            distrito=self.subido_por.seccion.distrito if self.subido_por.seccion else self.subido_por.distrito,
            seccion=self.subido_por.seccion
        )

    def save(self, *args, **kwargs):
        """
        Actualiza el hash de la imágen original asociada antes de guardar.
        Notar que esto puede puede producir una excepción si la imágen (el digest)
        ya es conocido en el sistema.

        Además, crea una PreIdentificacion con los datos del Fiscal que lo subió si no hay una.
        """
        if self.foto and not self.foto_digest:
            # FIXME
            # Sólo se calcula el digest cuando no hay uno previo.
            # esto impide recalcular el digest si eventualmente cambia
            # la imagen por algun motivo
            # Mejor seria verificar con un MonitorField si la foto cambió
            # y sólo en ese caso actualizar el hash.
            self.foto.file.open()
            self.foto_digest = hash_file(self.foto.file)
        self.crear_pre_identificacion_si_corresponde()
        super().save(*args, **kwargs)

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
        return f'{self.id} {self.foto} ({self.mimetype})'


class Identificacion(TimeStampedModel):
    """
    Es el modelo que guarda clasificaciones de actas para asociarlas a mesas
    """
    STATUS = Choices(
        'identificada',
        'problema'
    )
    status = StatusField(choices_name='STATUS', choices=STATUS)

    SOURCES = Choices('web', 'csv', 'telegram')
    source = StatusField(choices_name='SOURCES', default=SOURCES.web)

    fiscal = models.ForeignKey('fiscales.Fiscal', blank=True, on_delete=models.CASCADE)
    mesa = models.ForeignKey(
        'elecciones.Mesa', related_name='identificaciones', null=True, blank=True, on_delete=models.SET_NULL
    )
    attachment = models.ForeignKey(
        Attachment, related_name='identificaciones', on_delete=models.CASCADE
    )
    procesada = models.BooleanField(default=False)
    invalidada = models.BooleanField(default=False)

    def __str__(self):
        return (
            f'id: {self.id} - {self.status} - {self.mesa} - {self.fiscal} - '
            f'procesada: {self.procesada} - invalidada: {self.invalidada}'
        )

    def invalidar(self):
        logger.info('Identificación invalidada', id=self.id)
        self.invalidada = True
        self.procesada = False
        self.save(update_fields=['invalidada', 'procesada'])

    def save(self, *args, **kwargs):
        """
        Si el fiscal es troll, la identificación nace invalidada y ya procesada.
        """
        if self.id is None and self.fiscal is not None and self.fiscal.troll:
            self.invalidada = True
            self.procesada = True
        super().save(*args, **kwargs)


class PreIdentificacion(TimeStampedModel):
    """
    Este modelo se usa para asociar a los attachment información de identificación que no es completa.
    No confundir con Identificacion ni con el status de identificación de una mesa.
    """

    fiscal = models.ForeignKey(
        'fiscales.Fiscal', null=True, blank=True, on_delete=models.SET_NULL
    )
    # La información se guarda indenpendientemente del fiscal porque el fiscal puede mudarse
    # o estar subiendo actas de otro lado.
    distrito = models.ForeignKey(
        'elecciones.Distrito', on_delete=models.CASCADE, null=True
    )
    seccion = models.ForeignKey(
        'elecciones.Seccion', null=True, blank=True, on_delete=models.SET_NULL
    )
    circuito = models.ForeignKey(
        'elecciones.Circuito', null=True, blank=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return f'{self.distrito} - {self.seccion} - {self.circuito} (subida por {self.fiscal})'


class CSVTareaDeImportacion(TimeStampedModel):

    csv_file = models.FileField()

    STATUS = Choices(
        'pendiente',
        'en_progreso',
        'procesado',
        'error'
    )

    status = StatusField(choices_name='STATUS', choices=STATUS, default=STATUS.pendiente)
    errores = models.TextField(null=True, blank=True, default=None)
    fiscal = models.ForeignKey(
        'fiscales.Fiscal', null=True, blank=True, on_delete=models.SET_NULL
    )

    mesas_total_ok = models.PositiveIntegerField(default=0)
    mesas_parc_ok = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)  # Se graba ante cada cambio.

    def cambiar_status(self, status):
        self.status = status
        self.save(update_fields=['status'])

    def fin_procesamiento(self, cant_mesas_ok, cant_mesas_parcialmente_ok):
        self.mesas_total_ok = cant_mesas_ok
        self.mesas_parc_ok = cant_mesas_parcialmente_ok
        self.status = CSVTareaDeImportacion.STATUS.procesado
        self.save(update_fields=['mesas_total_ok', 'mesas_parc_ok', 'status'])

    def save_errores(self):
        self.save(update_fields=['errores'])

    def __str__(self):
        return f'{self.id} - {self.csv_file}'
