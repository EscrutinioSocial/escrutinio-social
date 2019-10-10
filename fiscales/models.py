import re
import uuid
import random
import string
from django.db import models
from django.urls import reverse
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models import Sum
from django.db.models.signals import post_save, pre_delete
from django.contrib.contenttypes.models import ContentType
from annoying.functions import get_object_or_None
from elecciones.models import Seccion, Distrito, MesaCategoria

from contacto.models import DatoDeContacto
from adjuntos.models import Attachment
from model_utils.models import TimeStampedModel
from model_utils.fields import StatusField
from django.db.utils import IntegrityError
from model_utils import Choices
from django.contrib.auth.models import Group

from antitrolling.models import (
    marcar_explicitamente_fiscal_troll,
    marcar_explicitamente_fiscal_no_troll
)
from antitrolling.efecto import efecto_determinacion_fiscal_troll


class CodigoReferido(TimeStampedModel):
    # hay al menos 1 código de referido por fiscal
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
        codigo_ref = get_object_or_None(CodigoReferido, codigo=codigo.upper())
        if codigo_ref and codigo_ref.activo:
            # codigo valido vigente
            return [(codigo_ref.fiscal, 100)]
        if codigo_ref and not codigo_ref.activo:
            # codigo valido no activo
            return [(codigo_ref.fiscal, 25)]
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


class FiscalManager(models.Manager):
    def get_by_natural_key(self, tipo_dni, dni):
        return self.get(tipo_dni=tipo_dni, dni=dni)


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
    puntaje_scoring_troll = models.IntegerField(null=False, default=0)
    troll = models.BooleanField(null=False, default=False)
    user = models.OneToOneField(
        'auth.User', null=True, blank=True, related_name='fiscal', on_delete=models.SET_NULL
    )
    seccion = models.ForeignKey(Seccion, related_name='fiscal', null=True, blank=True, on_delete=models.SET_NULL)

    # Campos para control de doble logueo.
    session_key = models.CharField(max_length=32, null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    distrito = models.ForeignKey(Distrito, related_name='fiscal', null=True, blank=True, on_delete=models.SET_NULL)

    referente = models.ForeignKey('Fiscal', related_name='referidos', null=True, blank=True, on_delete=models.SET_NULL)
    referente_certeza = models.PositiveIntegerField(default=100, help_text='El código no era exacto?')
    # Se pone en true cuando quien lo refirió indica que sí lo conoce.
    referencia_confirmada = models.BooleanField(default=False)

    # otra metadata del supuesto referente
    referente_nombres = models.CharField(max_length=100, blank=True, null=True)
    referente_apellido = models.CharField(max_length=50, blank=True, null=True)

    # el materialized path de referencias
    referido_por_codigos = models.CharField(max_length=250, blank=True, null=True)

    # Para saber si hay que capacitarlo
    ingreso_alguna_vez = models.BooleanField(default=False)

    # Campos para saber qué attachment o mesa tiene asignado.
    asignacion_ultima_tarea = models.DateTimeField(null=True, blank=True)
    attachment_asignado = models.ForeignKey(Attachment, related_name='fiscal_asignado', null=True, blank=True, on_delete=models.SET_NULL)
    mesa_categoria_asignada = models.ForeignKey(MesaCategoria, related_name='fiscal_asignado', null=True, blank=True, on_delete=models.SET_NULL)

    # Distrito en el que estuvo trabajando hasta ahora.
    distrito_afin = models.ForeignKey(Distrito, null=True, blank=True, on_delete=models.SET_NULL, related_name='fiscal_afin')
    
    class Meta:
        verbose_name_plural = 'Fiscales'
        unique_together = (('tipo_dni', 'dni'), )

    objects = FiscalManager()

    @classmethod
    def liberar_mesacategorias_y_attachments(cls):
        """
        Toma a los fiscales cuya última tarea haya sido asignada más de
        `settings.TIMEOUT_TAREAS` minutos atrás y:
        - No se la desasigna para no perder el trabajo que el fiscal puede estar haciendo y 'presentará'
        cuando haga el submit.
        - Pero sí le baja la cantidad de asignaciones a la mesacategoría y los attachments para que queden
        postergados por demasiado tiempo.
        """
        desde = timezone.now() - timedelta(minutes=settings.TIMEOUT_TAREAS)
        fiscales_para_limpiar_asignacion_previa = []
        with transaction.atomic():
            fiscales_con_timeout = Fiscal.objects.select_for_update(skip_locked=True).filter(
                asignacion_ultima_tarea__lt=desde)
            for fiscal in fiscales_con_timeout:
                fiscal.resetear_timeout_asignacion_tareas()
                fiscales_para_limpiar_asignacion_previa.append(fiscal)

        # Por fuera de la transacción realizamos la limpieza de las mesascat o
        # attachments que tuviera asignados, para evitar deadlocks (ver #321).
        for fiscal in fiscales_para_limpiar_asignacion_previa:
            fiscal.limpiar_asignacion_previa()

    def limpiar_asignacion_previa(self):
        """
        Este método se utiliza para que las mesa-categorías o attachments
        que tenga asignados el fiscal sean liberados cuando corresponda
        (por timeout o cuando se asigna uno nuevo).

        No se la desasigna para no perder el trabajo que el fiscal puede estar haciendo y 'presentará'
        cuando haga el submit.
        """
        if self.attachment_asignado:
            self.attachment_asignado.desasignar_a_fiscal()
        elif self.mesa_categoria_asignada:
            self.mesa_categoria_asignada.desasignar_a_fiscal()

    def asignar_attachment(self, attachment):
        """
        Asigna al fiscal un attachment para que trabaje en él.

        Tiene como prerrequisito que se hayan hecho un llamado previo a
        limpiar_asignacion_previa() para desasignar la asignación anterior.
        No se hace aquí para evitar deadlocks (ver #317), se hace desde
        acciones.py en una transacción independiente.
        """
        distrito = attachment.distrito_preidentificacion
        self.asignar_attachment_o_mesacategoria(attachment, None, distrito)

    def asignar_mesa_categoria(self, mesa_categoria):
        """
        Asigna al fiscal una mesa_categoria para que trabaje en ella.

        Tiene como prerrequisito que se hayan hecho un llamado previo a
        limpiar_asignacion_previa() para desasignar la asignación anterior.
        No se hace aquí para evitar deadlocks (ver #317), se hace desde
        acciones.py en una transacción independiente.
        """
        distrito = mesa_categoria.mesa.distrito
        self.asignar_attachment_o_mesacategoria(None, mesa_categoria, distrito)

    def asignar_attachment_o_mesacategoria(self, attachment, mesa_categoria, distrito_afin=None):
        self.attachment_asignado = attachment
        self.mesa_categoria_asignada = mesa_categoria
        self.distrito_afin = distrito_afin
        self.asignacion_ultima_tarea = timezone.now()
        self.save(update_fields=[
            'asignacion_ultima_tarea',
            'attachment_asignado',
            'mesa_categoria_asignada',
            'distrito_afin'
        ])

    def resetear_timeout_asignacion_tareas(self):
        self.asignacion_ultima_tarea = None
        self.save(update_fields=['asignacion_ultima_tarea'])

    def update_last_seen(self, cuando):
        self.last_seen = cuando
        self.save(update_fields=['last_seen'])

    def update_session_key(self, session_key):
        self.session_key = session_key
        self.save(update_fields=['session_key'])

    def crear_codigo_de_referidos(self):
        self.codigos_de_referidos.filter(activo=True).update(activo=False)
        return CodigoReferido.objects.create(fiscal=self)

    def ultimo_codigo(self):
        """devuelve el último código activo"""
        cod_ref = self.codigos_de_referidos.filter(activo=True).last()
        if cod_ref:
            return cod_ref.codigo

    def ultimo_codigo_url(self):
        """
        devuelve la url absoluta con último código activo
        """
        url = reverse('quiero-validar', args=[self.ultimo_codigo()])
        return f'{settings.FULL_SITE_URL}{url}'

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

    def scoring_troll(self):
        return self.puntaje_scoring_troll

    def cambiar_scoring_troll(self, variacion):
        self.puntaje_scoring_troll += variacion
        self.save(update_fields=['puntaje_scoring_troll'])

    def marcar_como_troll(self, actor):
        """
        Un UE decidió, explícitamente, marcarme como troll
        """
        marcar_explicitamente_fiscal_troll(self, actor)

    def quitar_marca_troll(self, actor, nuevo_scoring):
        """
        Un UE decidió, explícitamente, indicar que no soy troll
        """
        marcar_explicitamente_fiscal_no_troll(self, actor, nuevo_scoring)

    def marcar_ingreso_alguna_vez(self):
        """
        Marca que el Fiscal efectivamente ya ingresó alguna vez.
        En principio la marca de ingreso_alguna_vez se usa para capacitar al validador.
        """
        self.ingreso_alguna_vez = True
        self.save(update_fields=['ingreso_alguna_vez'])

    def natural_key(self):
        return (self.tipo_dni, self.dni)
    natural_key.dependencies = ['elecciones.distrito', 'elecciones.seccion', 'auth.user']

    @classmethod
    def destrolleo_masivo(cls, actor, hasta_scoring, nuevo_scoring):
        for fiscal in Fiscal.objects.filter(troll=True).filter(puntaje_scoring_troll__lte=hasta_scoring):
            fiscal.quitar_marca_troll(actor, nuevo_scoring)


@receiver(post_save, sender=Fiscal)
def crear_user_y_codigo_para_fiscal(sender, instance=None, created=False, update_fields=None, **kwargs):
    """
    Cuando se crea o actualiza una instancia de ``Fiscal`` en estado confirmado
    que no tiene usuario asociado, automáticamente se crea uno ``auth.User``
    utilizando el DNI como `username`.
    """
    if 'last_seen' in update_fields and len(update_fields) == 1:
        # Si sólo se actualiza el last_seen no hacemos nada más.
        return

    if not instance.user and instance.dni and instance.estado in ('AUTOCONFIRMADO', 'CONFIRMADO'):
        user = User(
            username=re.sub("[^0-9]", "", instance.dni),
            first_name=instance.nombres,
            last_name=instance.apellido,
            is_active=True,
            email=instance.emails[0] if instance.emails else ""
        )

        user.save()
        instance.user = user
        instance.save(update_fields=['user'])
    if not instance.codigos_de_referidos.exists():
        instance.crear_codigo_de_referidos()


@receiver(pre_delete, sender=Fiscal)
def borrar_user_para_fiscal(sender, instance=None, **kwargs):
    if instance.user:
        instance.user.delete()
