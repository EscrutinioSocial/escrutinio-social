import re
import uuid
import random
import string
from django.db import models
from django.conf import settings
from django.db import transaction
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_delete
from django.contrib.contenttypes.models import ContentType
from annoying.functions import get_object_or_None
from elecciones.models import Seccion

from contacto.models import DatoDeContacto
from model_utils.models import TimeStampedModel
from model_utils.fields import StatusField
from django.db.utils import IntegrityError
from model_utils import Choices
from django.contrib.auth.models import Group

TOTAL = 'Total General'


class CodigoReferido(TimeStampedModel):
    # hay al menos 1 codigo de referido por fiscal
    fiscal = models.ForeignKey('Fiscal', related_name='codigos_de_referidos', on_delete=models.CASCADE)
    codigo = models.CharField(
        max_length=4, unique=True, help_text='Código con el que el fiscal puede referir a otres'
    )
    activo = models.BooleanField(default=True)

    @classmethod
    def fiscales_para(cls, codigo, nombre=None, apellido=None):
        """
        Devuelve una lista de fiscales candidatos
        """
        codigo_ref = get_object_or_None(CodigoReferido, codigo=codigo, activo=True)
        # TO DO. encontrar fiscal candidato basado en un código similar
        # http://andilabs.github.io/2018/04/06/searching-in-django-unaccent-levensthein-full-text-search-postgres-power.html
        # restar 25% por cada grado de distancia Levenshtein
        if codigo_ref:
            return [(codigo_ref.fiscal, 100)]
        elif nombre and apellido:
            qs = Fiscal.objects.filter(nombres__icontains=nombre, apellido__icontains=apellido)
            if qs.exists():
                return [(f, 75) for f in qs]
        return [(None, 100)]

    def save(self, *args, **kwargs):
        """
        Genera un código único de 4 dígitos alfanuméricos
        """
        intentos = 5
        while True:
            intentos -= 1
            try:
                if not self.codigo:
                    self.codigo = ''.join(random.sample(string.ascii_uppercase + string.digits, 4))
                with transaction.atomic():
                    super().save(*args, kwargs)
                break
            except IntegrityError:
                self.codigo = None
                # se crea un código random unico.
                # Si falla muchas veces algo feo está pasando.
                if intentos:
                    continue
                raise


class Fiscal(models.Model):
    """
    Representa al usuario "data-entry" del sistema.
    Es una extensión del modelo ``auth.User``

    """
    TIPO_DNI = Choices('DNI', 'CI', 'LE', 'LC')
    ESTADOS = Choices('IMPORTADO', 'AUTOCONFIRMADO', 'PRE-INSCRIPTO', 'CONFIRMADO', 'DECLINADO')

    # Actualmente no se consideran los diferentes estados
    # salvo para la creación del user asociado.
    estado = StatusField(choices_name='ESTADOS', default='PRE-INSCRIPTO')
    notas = models.TextField(blank=True, help_text='Notas internas, no se muestran')
    codigo_confirmacion = models.UUIDField(default=uuid.uuid4, editable=False)
    email_confirmado = models.BooleanField(default=False)
    apellido = models.CharField(max_length=50)
    nombres = models.CharField(max_length=100)
    tipo_dni = models.CharField(choices=TIPO_DNI, max_length=3, default='DNI')
    dni = models.CharField(max_length=15, blank=True, null=True)
    datos_de_contacto = GenericRelation('contacto.DatoDeContacto', related_query_name='fiscales')
    user = models.OneToOneField(
        'auth.User', null=True, blank=True, related_name='fiscal', on_delete=models.SET_NULL
    )
    seccion = models.ForeignKey(Seccion, related_name='fiscal', null=True, blank=True, on_delete=models.SET_NULL)

    referente = models.ForeignKey('Fiscal', null=True, blank=True, on_delete=models.SET_NULL)
    referente_certeza = models.PositiveIntegerField(default=100, help_text='El código no era exacto?')
    # otra metadata del supuesto referente
    referente_nombres = models.CharField(max_length=50, blank=True, null=True)
    referente_apellido = models.CharField(max_length=30, blank=True, null=True)

    # el materialized path de referencias
    referido_por_codigos = models.CharField(max_length=250, blank=True, null=True)


    class Meta:
        verbose_name_plural = 'Fiscales'
        unique_together = (('tipo_dni', 'dni'), )

    def crear_codigo_de_referidos(self):
        return CodigoReferido.objects.create(fiscal=self)

    def agregar_dato_de_contacto(self, tipo, valor):
        type_ = ContentType.objects.get_for_model(self)
        try:
            DatoDeContacto.objects.get(content_type__pk=type_.id, object_id=self.id, tipo=tipo, valor=valor)
        except DatoDeContacto.DoesNotExist:
            DatoDeContacto.objects.create(content_object=self, tipo=tipo, valor=valor)

    @property
    def telefonos(self):
        return self.datos_de_contacto.filter(tipo='teléfono').values_list('valor', flat=True)

    @property
    def emails(self):
        return self.datos_de_contacto.filter(tipo='email').values_list('valor', flat=True)

    def __str__(self):
        return f'{self.nombres} {self.apellido}'

    def esta_en_grupo(self, nombre_grupo):
        grupo = Group.objects.get(name=nombre_grupo)

        return grupo in self.user.groups.all()

    def esta_en_algun_grupo(self, nombres_grupos):
        for nombre in nombres_grupos:
            try:
                grupo = Group.objects.get(name=nombre)
                if grupo in self.user.groups.all():
                    return True
            except Group.DoesNotExist:
                continue
        return False

    # Especializaciones para usar desde los templates.
    @property
    def esta_en_grupo_validadores(self):
        return self.esta_en_grupo('validadores')

    @property
    def esta_en_grupo_visualizadores(self):
        return self.esta_en_grupo('visualizadores')

    @property
    def esta_en_grupo_unidades_basicas(self):
        return self.esta_en_grupo('unidades basicas')


@receiver(post_save, sender=Fiscal)
def crear_user_y_codigo_para_fiscal(sender, instance=None, created=False, **kwargs):
    """
    Cuando se crea o actualiza una instancia de ``Fiscal`` en estado confirmado
    que no tiene usuario asociado, automáticamente se crea uno ``auth.User``
    utilizando el DNI como `username`.
    """
    if not instance.user and instance.dni and instance.estado in ('AUTOCONFIRMADO', 'CONFIRMADO'):
        user = User(
            username=re.sub("[^0-9]", "", instance.dni),
            first_name=instance.nombres,
            last_name=instance.apellido,
            is_active=True,
            email=instance.emails[0] if instance.emails else ""
        )

        # user.set_password(settings.DEFAULT_PASS_PREFIX + instance.dni[-3:])
        user.save()
        instance.user = user
        instance.save(update_fields=['user'])
    if not instance.codigos_de_referidos.exists():
        instance.crear_codigo_de_referidos()



@receiver(pre_delete, sender=Fiscal)
def borrar_user_para_fiscal(sender, instance=None, **kwargs):
    if instance.user:
        instance.user.delete()
