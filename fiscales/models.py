import re
import uuid
from django.db import models
from django.conf import settings
from django.db.models import Q
from django.contrib.contenttypes.fields import GenericRelation
from model_utils import Choices
from model_utils.models import TimeStampedModel
from django.utils import timezone
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_delete
from elecciones.models import desde_hasta, Mesa, LugarVotacion, Eleccion
from django.contrib.contenttypes.models import ContentType
from contacto.models import DatoDeContacto
from model_utils.fields import StatusField
from model_utils import Choices


TOTAL = 'Total General'



class Organizacion(models.Model):
    nombre = models.CharField(max_length=100)
    referentes = models.ManyToManyField('Fiscal', related_name='es_referente_de_orga', blank=True)

    class Meta:
        verbose_name = 'Organización'
        verbose_name_plural = 'Organizaciones'

    def __str__(self):
        return self.nombre



class Fiscal(models.Model):
    TIPO = Choices(('general', 'General'), ('de_mesa', 'de Mesa'))
    TIPO_DNI = Choices('DNI', 'CI', 'LE', 'LC')
    ESTADOS = Choices('IMPORTADO', 'AUTOCONFIRMADO', 'PRE-INSCRIPTO', 'CONFIRMADO', 'DECLINADO')
    DISPONIBILIDAD = Choices('mañana', 'tarde', 'todo el día')

    estado = StatusField(choices_name='ESTADOS', default='PRE-INSCRIPTO')
    notas = models.TextField(blank=True, help_text='Notas internas, no se muestran')
    escuela_donde_vota = models.ForeignKey('elecciones.LugarVotacion', verbose_name='Escuela preferida para fiscalizar', null=True, blank=True)
    disponibilidad = models.CharField(choices=DISPONIBILIDAD, max_length=20, blank=True)
    movilidad = models.NullBooleanField(help_text='Movilidad propia')
    tipo = models.CharField(choices=TIPO, max_length=20)
    codigo_confirmacion = models.UUIDField(default=uuid.uuid4, editable=False)
    email_confirmado = models.BooleanField(default=False)
    apellido = models.CharField(max_length=50)
    nombres = models.CharField(max_length=100)
    direccion = models.CharField(max_length=200, blank=True)
    barrio = models.CharField(max_length=200, blank=True)
    localidad = models.CharField(max_length=200, blank=True)
    tipo_dni = models.CharField(choices=TIPO_DNI, max_length=3, default='DNI')
    dni = models.CharField(max_length=15, blank=True, null=True)
    datos_de_contacto = GenericRelation('contacto.DatoDeContacto', related_query_name='fiscales')
    organizacion = models.ForeignKey('Organizacion', null=True, blank=True, help_text='Opcional. Para mostrar contactos extra del usuario')
    user = models.OneToOneField('auth.User', null=True,
                    blank=True, related_name='fiscal',
                    on_delete=models.SET_NULL)


    class Meta:
        verbose_name_plural = 'Fiscales'
        unique_together = (('tipo_dni', 'dni'),)

    def agregar_dato_de_contacto(self, tipo, valor):
        type_ = ContentType.objects.get_for_model(self)
        try:
            DatoDeContacto.objects.get(content_type__pk=type_.id, object_id=self.id, tipo=tipo, valor=valor)
        except DatoDeContacto.DoesNotExist:
            DatoDeContacto.objects.create(content_object=self, tipo=tipo, valor=valor)

    @property
    def es_general(self):
        return self.tipo == Fiscal.TIPO.general

    @property
    def es_referente(self):
        return self.es_referente_de_circuito.exists()

    @property
    def telefonos(self):
        return self.datos_de_contacto.filter(tipo='teléfono').values_list('valor', flat=True)

    @property
    def emails(self):
        return self.datos_de_contacto.filter(tipo='email').values_list('valor', flat=True)

    @property
    def mesas_asignadas(self):
        eleccion = Eleccion.actual()
        if self.es_general:
            return Mesa.objects.filter(
                eleccion=eleccion,
                lugar_votacion__asignacion__fiscal=self,
                lugar_votacion__asignacion__eleccion=eleccion
            ).order_by('numero')
        return Mesa.objects.filter(
            eleccion=eleccion,
            asignacion__fiscal=self
        ).order_by('numero')

    @property
    def escuelas(self):
        if self.es_general:
            return LugarVotacion.objects.filter(
                asignacion__fiscal=self,
                asignacion__eleccion__id=1
            ).distinct()
        else:
            return LugarVotacion.objects.filter(mesas__eleccion__id=1, mesas__asignacion__fiscal=self).distinct()

    @property
    def circuitos(self):
        return {e.circuito for e in self.escuelas}

    @property
    def asignacion(self):
        if self.es_general:
            qs = AsignacionFiscalGeneral.objects.filter(fiscal=self, eleccion__id=1)
        else:
            qs = AsignacionFiscalDeMesa.objects.filter(fiscal=self, mesa__eleccion__id=1)
        return qs.last()

    @property
    def label_from_instance(self):
        if self.asignacion:
            return f'{self} (asignado a {self.asignacion.asignable})'
        return f'{self}'


    def asignar_a(self, asignable):
        if isinstance(asignable, Mesa):
            return AsignacionFiscalDeMesa.objects.get_or_create(mesa=asignable, fiscal=self)[0]
        elif isinstance(asignable, LugarVotacion):
            asignacion, _ = AsignacionFiscalGeneral.objects.create(
                lugar_votacion=asignable, fiscal=self
            )
            if not self.es_general:
                # gana privilegios :o
                self.tipo = Fiscal.TIPO.general
                self.save(update_fields['tipo'])
            return asignacion

    @property
    def direccion_completa(self):
        return f'{self.direccion} {self.barrio}, {self.localidad}'


    def fiscales_colegas(self):
        """fiscales en la misma escuela"""
        escuelas = self.escuelas.all()
        if escuelas:
            general = Q(tipo='general') & Q(asignacion_escuela__lugar_votacion__in=escuelas)
            de_mesa = Q(tipo='de_mesa') & Q(asignacion_mesa__mesa__lugar_votacion__in=escuelas)
            return Fiscal.objects.exclude(id=self.id).filter(general | de_mesa).order_by('-tipo')
        return Fiscal.objects.none()


    def referentes_de_circuito(self):
        if self.circuitos:
            return Fiscal.objects.exclude(id=self.id).filter(es_referente_de_circuito__in=self.circuitos)
        return Fiscal.objects.none()

    def referentes_de_orga(self):
        if self.organizacion:
            Fiscal.objects.exclude(id=self.id).filter(es_referente_de_orga=self.organizacion)
        return Fiscal.objects.none()

    @property
    def mesas_desde_hasta(self):
        return desde_hasta(self.mesas_asignadas)


    def tiempo_de_carga(self):
        result = self.votomesareportado_set.filter(opcion__nombre=TOTAL).order_by('-created')[:2]
        if result.count() == 2:
            return (result[0].created - result[1].created).total_seconds()
        return None



    def __str__(self):
        return f'{self.nombres} {self.apellido}'


class AsignacionFiscal(TimeStampedModel):
    ESTADOS_COMIDA = Choices('no asignada', 'asignada', 'recibida')
    ingreso = models.DateTimeField(null=True, editable=False)
    egreso = models.DateTimeField(null=True, editable=False)
    comida = models.CharField(choices=ESTADOS_COMIDA, max_length=50, default='no asignada')

    @property
    def esta_presente(self):
        if self.ingreso and not self.egreso:
            return True
        return False

    class Meta:
        abstract = True


class AsignacionFiscalDeMesa(AsignacionFiscal):
    mesa = models.ForeignKey(
        'elecciones.Mesa',
        limit_choices_to={'eleccion__id': 1},
        related_name='asignacion'
    )

    # es null si el fiscal general dice que la mesa está asignada
    # pero aun no hay datos.
    fiscal = models.ForeignKey('Fiscal', null=True, blank=True,
        limit_choices_to={'tipo': Fiscal.TIPO.de_mesa}, related_name='asignacion_mesa')


    @property
    def asignable(self):
        return self.mesa

    def __str__(self):
        if self.fiscal:
            return f'Asignacion {self.mesa}: {self.fiscal}'
        return f'Asignación {self.mesa}: registro sin datos'

    class Meta:
        verbose_name = 'Asignación de Fiscal de Mesa'
        verbose_name_plural = 'Asignaciones de Fiscal de Mesa'


class AsignacionFiscalGeneral(AsignacionFiscal):
    lugar_votacion = models.ForeignKey(
        'elecciones.LugarVotacion', related_name='asignacion')
    eleccion = models.ForeignKey('elecciones.Eleccion',
        limit_choices_to={'id': 1},
        default=1,
    )
    fiscal = models.ForeignKey('Fiscal',
        limit_choices_to={'tipo': Fiscal.TIPO.general},
        related_name='asignacion_escuela'
    )

    @property
    def asignable(self):
        return self.lugar_votacion

    def __str__(self):
        return f'{self.fiscal} {self.lugar_votacion}'

    class Meta:
        verbose_name = 'Asignación de Fiscal General'
        verbose_name_plural = 'Asignaciones de Fiscal General'


@receiver(post_save, sender=Fiscal)
def crear_user_para_fiscal(sender, instance=None, created=False, **kwargs):
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


@receiver(post_save, sender=DatoDeContacto)
def fiscal_contacto(sender, instance=None, created=False, **kwargs):
    # metadata de user con datos de contacto
    if (instance.tipo == 'teléfono' and isinstance(instance.content_object, Fiscal) and not
            instance.content_object.user and
            instance.content_object.estado in ('AUTOCONFIRMADO', 'CONFIRMADO')):
        # si no tiene usuario y se asigna telefono, usar este dato
        fiscal = instance.content_object
        rawnumber = ''.join(instance.valor.split()[-2:]).replace('-', '')

        user = User(
            username=rawnumber,
            first_name=fiscal.nombres,
            last_name=fiscal.apellido,
            is_active=True,
        )
        # user.set_password(settings.DEFAULT_PASS_PREFIX + rawnumber[-3:])
        user.save()

        fiscal.user = user
        fiscal.save(update_fields=['user'])

    if (instance.tipo == 'email' and
            isinstance(instance.content_object, Fiscal) and
            instance.content_object.user and not
            instance.content_object.user.email):
        user = instance.content_object.user
        user.email = instance.valor
        user.save(update_fields=['email'])



@receiver(pre_delete, sender=Fiscal)
def borrar_user_para_fiscal(sender, instance=None, **kwargs):
    if instance.user:
        instance.user.delete()
