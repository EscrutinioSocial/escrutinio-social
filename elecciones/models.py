import os
from itertools import chain
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.urls import reverse
from django.db import models
from django.db.models import Sum, IntegerField, Case, Value, When, F, Q, Count, OuterRef, Subquery, Exists, Max, Value
from django.db.models.functions import Coalesce
from django.conf import settings
from djgeojson.fields import PointField
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.dispatch import receiver
from django.db.models.signals import m2m_changed, post_save
from model_utils.fields import StatusField, MonitorField
from model_utils.models import TimeStampedModel
from model_utils import Choices
from adjuntos.models import Attachment
from problemas.models import Problema


class Seccion(models.Model):
    # O departamento
    numero = models.PositiveIntegerField(null=True)
    nombre = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'Sección electoral'
        verbose_name_plural = 'Secciones electorales'


    def resultados_url(self):
        return reverse('resultados-eleccion') + f'?seccion={self.id}'


    def __str__(self):
        return f"{self.numero} - {self.nombre}"

    def mesas(self, eleccion):
        return Mesa.objects.filter(
            lugar_votacion__circuito__seccion=self,
            eleccion=eleccion
    )

    @property
    def electores(self):
        return Mesa.objects.filter(
            lugar_votacion__circuito__seccion=self,
        ).aggregate(v=Sum('electores'))['v']

    @property
    def peso(self):
        return self.electores / Eleccion.actual().electores


class AgrupacionPK(models.Model):
    # una agrupacion de circuitos interna
    numero = models.PositiveIntegerField()
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.numero} - {self.nombre}"

    @property
    def electores(self):
        return Mesa.objects.filter(
            lugar_votacion__circuito__agrupacionpk=self,
        ).aggregate(v=Sum('electores'))['v']


class Circuito(models.Model):
    seccion = models.ForeignKey(Seccion)
    seccion_de_ponderacion = models.ForeignKey(AgrupacionPK, null=True)
    localidad_cabecera = models.CharField(max_length=100, null=True, blank=True)

    numero = models.CharField(max_length=10)
    nombre = models.CharField(max_length=100)


    class Meta:
        verbose_name = 'Circuito electoral'
        verbose_name_plural = 'Circuitos electorales'
        ordering = ('id',)

    def __str__(self):
        return f"{self.numero} - {self.nombre}"

    @property
    def electores(self):
        return Mesa.objects.filter(
            lugar_votacion__circuito=self,
        ).aggregate(v=Sum('electores'))['v']

    @property
    def peso(self):
        return self.electores / Eleccion.actual().electores

    def resultados_url(self):
        return reverse('resultados-eleccion') + f'?circuito={self.id}'

    def proximo_orden_de_carga(self):
        orden = Mesa.objects.exclude(id=self.id).filter(
            lugar_votacion__circuito=self
        ).aggregate(v=Max('orden_de_carga'))['v'] or 0
        return orden + 1

    def mesas(self, eleccion):
        return Mesa.objects.filter(
            lugar_votacion__circuito=self,
            eleccion=eleccion
    )


class LugarVotacion(models.Model):
    circuito = models.ForeignKey(Circuito, related_name='escuelas')
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=100)
    barrio = models.CharField(max_length=100, blank=True)
    ciudad = models.CharField(max_length=100, blank=True)
    calidad = models.CharField(max_length=20, help_text='calidad de la geolocalizacion', editable=False, blank=True)
    electores = models.PositiveIntegerField(null=True, blank=True)
    geom = PointField(null=True)
    estado_geolocalizacion = models.PositiveIntegerField(default=0, help_text='Indicador (0-10) de que confianza hay en la geolozalización')

    # denormalizacion para hacer queries más simples
    latitud = models.FloatField(null=True, editable=False)
    longitud = models.FloatField(null=True, editable=False)

    class Meta:
        verbose_name = 'Lugar de votación'
        verbose_name_plural = "Lugares de votación"


    def get_absolute_url(self):
        url = reverse('donde-fiscalizo')
        return f'{url}#donde{self.id}'


    def save(self, *args, **kwargs):

        if self.geom:
            self.longitud, self.latitud = self.geom['coordinates']
        else:
            self.longitud, self.latitud = None, None
        super().save(*args, **kwargs)

    @property
    def coordenadas(self):
        return f'{self.latitud},{self.longitud}'

    @property
    def direccion_completa(self):
        return f'{self.direccion} {self.barrio} {self.ciudad}'

    @property
    def mesas_desde_hasta(self):
        qs = self.mesas
        qs = qs.values_list('numero', flat=True).order_by('numero')
        inicio, fin = qs.first(), qs.last()
        if inicio == fin:
            return inicio
        return f'{inicio} - {fin}'

    def mesas(self, eleccion):
        return Mesa.objects.filter(
            lugar_votacion=self,
            eleccion=eleccion
    )

    @property
    def mesas_actuales(self):
        return self.mesas.filter(eleccion=Eleccion.actual())

    @property
    def color(self):
        if VotoMesaReportado.objects.filter(mesa__lugar_votacion=self).exists():
            return 'green'
        return 'orange'

    @property
    def seccion(self):
        return str(self.circuito.seccion)


    def __str__(self):
        return f"{self.nombre} - {self.circuito}"


def path_foto_acta(instance, filename):
    # file will be uploaded to MEDIA_ROOT/
    _, ext = os.path.splitext(filename)
    return 'actas/{}/{}{}'.format(
        instance.eleccion.slug,
        instance.numero,
        ext
    )


class MesaEleccion(models.Model):
    mesa = models.ForeignKey('Mesa')
    eleccion = models.ForeignKey('Eleccion')
    confirmada = models.BooleanField(default=False)

    class Meta:
        unique_together = ('mesa', 'eleccion')



class Mesa(models.Model):
    ESTADOS_ = ('EN ESPERA', 'ABIERTA', 'CERRADA', 'ESCRUTADA')
    ESTADOS = Choices(*ESTADOS_)
    estado = StatusField(choices_name='ESTADOS', default='EN ESPERA')
    hora_escrutada = MonitorField(monitor='estado', when=['ESCRUTADA'])

    eleccion = models.ManyToManyField('Eleccion', through='MesaEleccion')
    numero = models.PositiveIntegerField()
    es_testigo = models.BooleanField(default=False)
    circuito = models.ForeignKey(Circuito, null=True)
    lugar_votacion = models.ForeignKey(LugarVotacion, verbose_name='Lugar de votacion', null=True, related_name='mesas')
    url = models.URLField(blank=True, help_text='url al telegrama')
    electores = models.PositiveIntegerField(null=True, blank=True)
    taken = models.DateTimeField(null=True, editable=False)
    orden_de_carga = models.PositiveIntegerField(default=0, editable=False)
    carga_confirmada = models.BooleanField(default=False)

    # denormalizacion.
    # lleva la cuenta de las elecciones que se han cargado hasta el momento.
    # ver receiver actualizar_elecciones_cargadas_para_mesa()
    cargadas = models.PositiveIntegerField(default=0, editable=False)
    confirmadas = models.PositiveIntegerField(default=0, editable=False)

    def eleccion_add(self, eleccion):
        MesaEleccion.objects.get_or_create(mesa=self, eleccion=eleccion)


    def siguiente_eleccion_sin_carga(self):
        for eleccion in self.eleccion.order_by('id'):
            if not VotoMesaReportado.objects.filter(mesa=self, eleccion=eleccion).exists():
                return eleccion


    @classmethod
    def con_carga_pendiente(cls, wait=2):
        """
        Una mesa cargable es aquella que
           - no este tomada dentro de los ultimos `wait` minutos
           - no este marcada con problemas o todos su problemas esten resueltos
           - y tenga al menos una eleccion asociada que no tenga votosreportados para esa mesa
        """
        desde = timezone.now() - timedelta(minutes=wait)
        qs = cls.objects.filter(
            attachments__isnull=False,
            orden_de_carga__gte=1,
        ).filter(
            Q(taken__isnull=True) | Q(taken__lt=desde)
        ).annotate(
            a_cargar = Count('eleccion')
        ).filter(
            cargadas__lt=F('a_cargar')
        ).annotate(
            tiene_problemas=Exists(
                Problema.objects.filter(
                    Q(mesa__id=OuterRef('id')),
                    ~Q(estado='resuelto')
                )
            )
        ).filter(
            tiene_problemas=False
        ).distinct()
        return qs

    def siguiente_eleccion_a_confirmar(self):
        for me in MesaEleccion.objects.filter(mesa=self).order_by('eleccion'):
            if not me.confirmada and VotoMesaReportado.objects.filter(
                eleccion=me.eleccion, mesa=me.mesa
            ).exists():
                return me.eleccion

    @classmethod
    def con_carga_a_confirmar(cls):
        qs = cls.objects.filter(
            mesaeleccion__confirmada=False,
            cargadas__gte=1
        ).filter(
            confirmadas__lt=F('cargadas')
        ).distinct()
        return qs


    def get_absolute_url(self):
        return '#' # reverse('detalle-mesa', args=(self.eleccion.first().id, self.numero,))

    @property
    def asignacion_actual(self):
        return self.asignacion.order_by('-ingreso').last()

    @property
    def tiene_reporte(self):
        return self.votomesareportado_set.aggregate(Sum('votos'))['votos__sum']

    def fotos(self):
        fotos = []
        for i, a in enumerate(Attachment.objects.filter(mesa=self).order_by('-id'), 1):
            if a.foto_edited:
                fotos.append((f'Foto {i} (editada)', a.foto_edited))
            fotos.append((f'Foto {i} (original)', a.foto))
        return fotos

    @property
    def proximo_estado(self):
        if self.estado == 'ESCRUTADA':
            return self.estado
        pos = Mesa.ESTADOS_.index(self.estado)
        return Mesa.ESTADOS_[pos + 1]

    @property
    def grupo_tabla_proyecciones(self):
        mi_circuito = self.lugar_votacion.circuito
        return mi_circuito if mi_circuito.seccion.numero == 1 else mi_circuito.seccion

    def __str__(self):
        return f"Mesa {self.numero}"


class Partido(models.Model):
    orden = models.PositiveIntegerField(help_text='Orden opcion')
    numero = models.PositiveIntegerField(null=True, blank=True)
    codigo = models.CharField(max_length=10, help_text='Codigo de partido', null=True, blank=True)
    nombre = models.CharField(max_length=100)
    nombre_corto = models.CharField(max_length=30, default='')
    color = models.CharField(max_length=30, default='', blank=True)
    referencia = models.CharField(max_length=30, default='', blank=True)
    ordering = ['orden']


    def __str__(self):
        return self.nombre


class Opcion(models.Model):
    MOSTRABLES = list(range(1, 21))
    AGREGACIONES = {f'{id}': Sum(Case(When(opcion__id=id, then=F('votos')),
                             output_field=IntegerField())) for id in MOSTRABLES}

    nombre = models.CharField(max_length=100)
    nombre_corto = models.CharField(max_length=20, default='')
    partido = models.ForeignKey(Partido, null=True, blank=True, related_name='opciones')   # blanco, / recurrido / etc
    orden = models.PositiveIntegerField(
        help_text='Orden en la boleta', null=True, blank=True)
    obligatorio = models.BooleanField(default=False)
    es_contable = models.BooleanField(default=True)
    codigo_dne = models.PositiveIntegerField(null=True, blank=True, help_text='Nº asignado en la base de datos de resultados oficiales')


    class Meta:
        verbose_name = 'Opción'
        verbose_name_plural = 'Opciones'
        ordering = ['orden']


    @property
    def color(self):
        if self.partido:
            return self.partido.color or '#FFFFFF'
        return '#FFFFFF'


    def __str__(self):
        if self.partido:
            return f'{self.partido.codigo} - {self.nombre}' #  -- {self.partido.nombre_corto}
        return self.nombre


class Eleccion(models.Model):
    """este modelo representa una categoria electiva: gobernador, intendente de loma del orto, etc)"""
    slug = models.SlugField(max_length=100, unique=True)
    nombre = models.CharField(max_length=100)
    fecha = models.DateTimeField(blank=True, null=True)
    opciones = models.ManyToManyField(Opcion, related_name='elecciones')
    color = models.CharField(max_length=10, default='black', help_text='Color para css (red o #FF0000)')
    back_color = models.CharField(max_length=10, default='white', help_text='Color para css (red o #FF0000)')

    def get_absolute_url(self):
        return reverse('resultados-eleccion', args=[self.id])

    def opciones_actuales(self):
        return self.opciones.all().order_by('orden')

    @classmethod
    def actual(cls):
        return cls.objects.get(id=1)

    @property
    def electores(self):
        return Mesa.objects.filter(eleccion=self).aggregate(v=Sum('electores'))['v']

    class Meta:
        verbose_name = 'Elección'
        verbose_name_plural = 'Elecciones'

    def __str__(self):
        return self.nombre


class VotoMesaReportado(TimeStampedModel):
    mesa = models.ForeignKey(Mesa)
    eleccion = models.ForeignKey(Eleccion)
    opcion = models.ForeignKey(Opcion)
    votos = models.PositiveIntegerField(null=True)
    fiscal = models.ForeignKey('fiscales.Fiscal', null=True)


    class Meta:
        # unique_together = ('mesa', 'opcion', 'fiscal')
        # sólo vamos a permitir una carga por mesa.
        unique_together = ('mesa', 'eleccion', 'opcion')

    def __str__(self):
        return f"{self.mesa} - {self.opcion}: {self.votos}"


@receiver(post_save, sender=VotoMesaReportado)
def actualizar_elecciones_cargadas_para_mesa(sender, instance=None, created=False, **kwargs):
    mesa = instance.mesa
    elecciones_cargadas = VotoMesaReportado.objects.filter(mesa=mesa).values('eleccion').distinct().count()
    if mesa.cargadas != elecciones_cargadas:
        mesa.cargadas = elecciones_cargadas
        mesa.save(update_fields=['cargadas'])


@receiver(post_save, sender=MesaEleccion)
def actualizar_elecciones_confirmadas_para_mesa(sender, instance=None, created=False, **kwargs):
    if instance.confirmada:
        mesa = instance.mesa
        confirmadas = MesaEleccion.objects.filter(mesa=mesa, confirmada=True).count()
        if mesa.confirmadas != confirmadas:
            mesa.confirmadas = confirmadas
            mesa.save(update_fields=['confirmadas'])

