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
    hasher = hashlib.blake2b()
    for buf in iter(partial(file.read, block_size), b''):
        hasher.update(buf)
    return hasher.hexdigest()


class Email(models.Model):
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
    PROBLEMAS = Choices(
        'no es una foto válida',
        'no se entiende',
        # 'foto rotada',
    )

    email = models.ForeignKey('Email', null=True)
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

    mesa = models.ForeignKey('elecciones.Mesa', null=True, related_name='attachments')
    taken = models.DateTimeField(null=True)
    problema = models.CharField(max_length=100, null=True, blank=True, choices=PROBLEMAS)

    def save(self, *args, **kwargs):
        if self.foto:
            self.foto.file.open()
            self.foto_digest = hash_file(self.foto.file)
        super().save(*args, **kwargs)

    @classmethod
    def sin_asignar(cls, wait=10):
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
    cuando se clasifica el attach, se le asigna el orden siguiente del circuito
    """
    if instance.mesa and not instance.mesa.votomesareportado_set.exists():
        mesa = instance.mesa
        mesa.orden_de_carga = mesa.circuito.proximo_orden_de_carga()
        mesa.save(update_fields=['orden_de_carga'])
