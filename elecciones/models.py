import os
import logging

from itertools import chain
from collections import defaultdict
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.urls import reverse
from django.db import models
from django.db.models import (
    Sum, IntegerField, Case, Value, When, F, Q, Count, OuterRef,
    Exists, Max, Value
)
from django.db.models.query import QuerySet
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

logger = logging.getLogger("e-va");

class Distrito(models.Model):
    """
    Define el distrito o circunscripción electoral. Es la subdivisión más
    grande en una carta marina. En una elección provincial el distrito es único.

    **Distrito** -> Sección -> Circuito -> Lugar de votación -> Mesa
    """
    numero = models.PositiveIntegerField(null=True)
    nombre = models.CharField(max_length=100)
    electores = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Distrito electoral'
        verbose_name_plural = 'Distrito electorales'

    def __str__(self):
        return f"{self.numero} - {self.nombre}"


class Seccion(models.Model):
    """
    Define la sección electoral:

    Distrito -> **Sección** -> Circuito -> Lugar de votación -> Mesa
    """
    distrito = models.ForeignKey(
        Distrito, on_delete=models.CASCADE, related_name='secciones'
    )
    numero = models.PositiveIntegerField(null=True)
    nombre = models.CharField(max_length=100)
    electores = models.PositiveIntegerField(default=0)
    proyeccion_ponderada = models.BooleanField(
        default=False,
        help_text=(
            'Si está marcado, el cálculo de proyeccion se agrupará '
            'por circuitos para esta sección'
        )
    )

    class Meta:
        ordering = ('numero',)
        verbose_name = 'Sección electoral'
        verbose_name_plural = 'Secciones electorales'

    def resultados_url(self):
        return reverse('resultados-categoria') + f'?seccion={self.id}'

    def __str__(self):
        return f"{self.numero} - {self.nombre}"

    def mesas(self, categoria):
        return Mesa.objects.filter(
            lugar_votacion__circuito__seccion=self,
            categorias=categoria
        )


class Circuito(models.Model):
    """
    Define el circuito, perteneciente a una sección

    Distrito -> Sección -> **Circuito** -> Lugar de votación -> Mesa
    """
    seccion = models.ForeignKey(Seccion, on_delete=models.CASCADE)
    localidad_cabecera = models.CharField(max_length=100, null=True, blank=True)

    numero = models.CharField(max_length=10)
    nombre = models.CharField(max_length=100)
    electores = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Circuito electoral'
        verbose_name_plural = 'Circuitos electorales'
        ordering = ('id',)

    def __str__(self):
        return f"{self.numero} - {self.nombre}"

    def resultados_url(self):
        return reverse('resultados-categoria') + f'?circuito={self.id}'

    def proximo_orden_de_carga(self):
        """
        Busca el máximo orden de carga `n` en una mesa perteciente al circuito
        (esté o no cargada) y devuelve `n + 1`.

        Este nuevo orden de carga incrementado se asigna a la nueva mesa
        clasificada en func:`asignar_orden_de_carga`
        """
        orden = Mesa.objects.filter(
            lugar_votacion__circuito=self
        ).aggregate(v=Max('orden_de_carga'))['v'] or 0
        return orden + 1

    def mesas(self, categoria):
        """
        Devuelve las mesas asociadas a este circuito para una categoría dada
        """
        return Mesa.objects.filter(
            lugar_votacion__circuito=self,
            categorias=categoria
    )


class LugarVotacion(models.Model):
    """
    Define el lugar de votación (escuela) que pertenece a un circuito
    y contiene mesas.
    Tiene un representación geoespacial (point).

    Distrito -> Sección -> Circuito -> **Lugar de votación** -> Mesa
    """

    circuito = models.ForeignKey(Circuito, related_name='escuelas', on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=100)
    barrio = models.CharField(max_length=100, blank=True)
    ciudad = models.CharField(max_length=100, blank=True)

    # electores es una denormalización. debe coincidir con la sumatoria de
    # los electores de cada mesa de la escuela
    electores = models.PositiveIntegerField(null=True, blank=True)
    geom = PointField(null=True)

    # A veces, al importar datos, se realizan distintas iteraciones para geolocalizar
    # escuelas. Estos campos sirven para cuantificar la calidad y poder filtrar para
    # mejorar los valores de menor confianza
    estado_geolocalizacion = models.PositiveIntegerField(
        default=0, help_text='Indicador (0-10) de que confianza hay en la geolozalización'
    )
    calidad = models.CharField(
        max_length=20, help_text='calidad de la geolocalizacion', editable=False, blank=True
    )
    # denormalización para hacer queries más simples
    # se sincronizan con ``geom`` en el método save()
    latitud = models.FloatField(null=True, editable=False)
    longitud = models.FloatField(null=True, editable=False)

    class Meta:
        verbose_name = 'Lugar de votación'
        verbose_name_plural = "Lugares de votación"

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

    def mesas(self, categoria):
        """
        Devuelve las mesas asociadas a este lugar de votación para una categoría dada
        """
        return Mesa.objects.filter(
            lugar_votacion=self,
            categorias=categoria
    )

    @property
    def mesas_actuales(self):
        return self.mesas.filter(categorias=Categoria.actual())

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


class MesaCategoria(models.Model):
    """
    Modelo intermedio para la relación m2m ``Mesa.categorias``
    mantiene el estado de las `cargas`

    Permite guardar el booleano que marca la carga de esa
    "columna" como confirmada.
    """
    STATUS = Choices(
        'sin_cargar',                   # no hay cargas
        'parcial_sin_consolidar',       # carga parcial única (no csv) o no coincidente
        'parcial_consolidada_csv',      # no hay dos cargas mínimas coincidentes, pero una es de csv. 
        'parcial_en_conflicto',         # cargas parcial divergentes sin consolidar
        'parcial_consolidada_dc',       # carga parcial consolidada por doble carga
        'total_sin_consolidar',
        'total_consolidada_csv',
        'total_en_conflicto',
        'total_consolidada_dc',
    )
    status = StatusField(default='sin_cargar')
    mesa = models.ForeignKey('Mesa', on_delete=models.CASCADE)
    categoria = models.ForeignKey('Categoria', on_delete=models.CASCADE)

    # Carga que es representativa del estado actual.
    carga_testigo = models.ForeignKey(
        'Carga', related_name='es_testigo',
        null=True, blank=True, on_delete=models.SET_NULL
    )

    def firma_count(self):
        """
        Devuelve un diccionario que agrupa por tipo de carga y firmas.
        Este método se usa para testing solamente.
        Por ejemplo::

            {'total': {
                '1-10|2-2': 1,
                '1-10|2-1': 1'
             },
             'parcial': {
                '1-10': 1}
            }
        """
        qs = self.cargas.all()
        result = defaultdict(dict)
        for item in qs.values('firma', 'tipo').annotate(total=Count('firma')):
            result[item['tipo']][item['firma']] = item['total']
        return result

    class Meta:
        unique_together = ('mesa', 'categoria')

    def actualizar_status(self, status, carga_testigo):
        self.status = status
        self.carga_testigo = carga_testigo
        self.save(update_fields=['status', 'carga_testigo'])


class Mesa(models.Model):
    """
    Define la mesa de votación que pertenece a un class:`LugarDeVotación`.

    Sección -> Circuito -> Lugar de votación -> **Mesa**

    Está asociada a una o más categorías electivas para los cuales
    el elector habilitado debe elegir.

    Por ejemplo, la mesa 12 del circuito 1J de La Matanza, elige
    Presidente y Vice, Diputado de Prov de Buenos Aires e Intendente de La Matanza.
    """

    categorias = models.ManyToManyField('Categoria', through='MesaCategoria')
    numero = models.CharField(max_length=10)
    es_testigo = models.BooleanField(default=False)
    circuito = models.ForeignKey(Circuito, null=True, on_delete=models.SET_NULL)
    lugar_votacion = models.ForeignKey(
        LugarVotacion, verbose_name='Lugar de votacion',
        null=True, related_name='mesas', on_delete=models.CASCADE
    )
    url = models.URLField(blank=True, help_text='url al telegrama')
    electores = models.PositiveIntegerField(null=True, blank=True)
    taken = models.DateTimeField(null=True, editable=False)
    orden_de_carga = models.PositiveIntegerField(default=0, editable=False)

    # denormalizaciones
    # lleva la cuenta de las categorías que se han cargado hasta el momento.
    # ver receiver actualizar_categorias_cargadas_para_mesa()
    cargadas = models.PositiveIntegerField(default=0, editable=False)
    confirmadas = models.PositiveIntegerField(default=0, editable=False)

    def categoria_add(self, categoria):
        MesaCategoria.objects.get_or_create(mesa=self, categoria=categoria)

    def siguiente_categoria_sin_carga(self):
        for categoria in self.categorias.filter(activa=True).order_by('id'):
            if not Carga.objects.filter(
                mesa_categoria__mesa=self,
                mesa_categoria__categoria=categoria
            ).exists():
                return categoria

    def marcar_todas_las_categorias_cargadas(self):
        cantidad_categorias = self.categorias.filter(activa=True).count()
        logger.debug(f'marcando {cantidad_categorias} como marcadas en mesa {self.numero}')
        self.cargadas = cantidad_categorias
        self.save(update_fields=['cargadas'])

    def marcar_todas_las_categorias_confirmadas(self):
        cantidad_categorias = self.cargadas
        logger.debug(f'marcando {cantidad_categorias} como confirmadas en mesa {self.numero}')
        self.confirmadas = cantidad_categorias
        self.save(update_fields=['confirmadas'])


    @classmethod
    def con_carga_pendiente(cls, wait=2):
        """
        Una mesa cargable es aquella que
           - no esté tomada dentro de los últimos `wait` minutos,
           - no esté marcada con problemas o todos su problemas estén resueltos,
           - esté identificada,
           - y no tenga cargas consolidadas
           TODO no tenga cargas consolidadas con doble carga.
        """
        desde = timezone.now() - timedelta(minutes=wait)
        qs = cls.objects.filter(
            attachments__isnull=False,
            # TODO: falta que al menos uno de los attachments esté como STATUS.identificada
        ).filter(
            Q(taken__isnull=True) | Q(taken__lt=desde)
        ).annotate(
            a_cargar=Count('categorias', filter=Q(categorias__activa=True))
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


    def get_absolute_url(self):
        # TODO: Por ahora no hay una vista que muestre la carga de datos
        # para todas las categorias de una mesa

        # return reverse('detalle-mesa', args=(self.categoria.first().id, self.numero,))
        return '#'

    def fotos(self):
        """
        Devuelve una lista de tuplas (titulo, foto) asociados a la mesa, incluyendo
        cualquier version editada de una foto, para aquellos attachements que esten
        consolidados

        Este método se utiliza para alimentar las pestañas en la pantalla de carga
        de datos.
        """
        fotos = []
        for i, a in enumerate(
            self.attachments.filter(
                status='identificada'
            ).order_by('modified'), 1
        ):
            if a.foto_edited:
                fotos.append((f'Foto {i} (editada)', a.foto_edited))
            fotos.append((f'Foto {i} (original)', a.foto))
        return fotos

    def __str__(self):
        return str(self.numero)


class Partido(models.Model):
    """
    Representa un partido político o alianza, que contiene :py:class:`opciones <Opcion>`.
    """
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
    """
    Una opción es lo que puede elegir hacer
    el elector con voto para una categoría.

    Incluye las opciones partidarias (que redundan en votos positivos)
    o blanco, nulo, etc, que son opciones no positivas
    y no asociadas a partidos. También pueden ser opciones de "metainformación"
    del acta, como totales de votos positivos, votos válidos, etc,
    que si bien pueden calcularse indirectamente a partir de otros datos,
    a veces se prefiere cargar para minimizar las decisiones en quien carga datos.

    Más de una opción puede estar asociada al mismo partido,
    (por ejemplo varias listas de un espacio en una PASO)
    pero actualmente sus votos se computan agregados

    ver :issue:`48`
    """

    nombre = models.CharField(max_length=100)
    nombre_corto = models.CharField(max_length=20, default='')
    partido = models.ForeignKey(
        Partido, null=True, on_delete=models.SET_NULL, blank=True, related_name='opciones'
    )   # blanco, / recurrido / etc
    orden = models.PositiveIntegerField(
        help_text='Orden en la boleta', null=True, blank=True)
    es_contable = models.BooleanField(default=True)

    es_metadata = models.BooleanField(
        default=False,
        help_text="para campos que son tipo 'Total positivo, o Total votos'"
    )

    codigo_dne = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Nº asignado en la base de datos de resultados oficiales'
    )

    class Meta:
        verbose_name = 'Opción'
        verbose_name_plural = 'Opciones'
        ordering = ['orden']


    @property
    def color(self):
        """
        Devuelve el color del partido si existe o blanco.
        Permite destacar con un color la fila en la tabla de resultados
        """
        if self.partido and self.partido.color:
            return self.partido.color
        return '#FFFFFF'


    def __str__(self):
        if self.partido:
            return f'{self.partido.codigo} - {self.nombre}' #  -- {self.partido.nombre_corto}
        return self.nombre


class Eleccion(models.Model):
    """
    Es un modelo contenedor que representa, basicamente, un dia de elecciones.

    Contiene :py:class:`categorías <Categoria>`

    La finalidad que tiene es permitir la persistencia de resultados de multiples
    elecciones (por ejemplo PASO, primarias, balotaje) para hacer análisis
    """
    fecha = models.DateTimeField()
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.nombre}'

    class Meta:
        verbose_name = 'Elección'
        verbose_name_plural = 'Elecciones'


class Categoria(models.Model):
    """
    Representa una categoria electiva, es decir, una "columna" del acta.
    Por ejemplo: Presidente y Vicepresidente, Intendente de La Matanza, etc)

    Una categoría tiene habilitadas diferentes :py:meth:`opciones <Opcion>`
    que incluyen las partidarias (boletas) y blanco, nulo, etc.
    """
    eleccion = models.ForeignKey(Eleccion, null=True, on_delete=models.SET_NULL)
    slug = models.SlugField(max_length=100, unique=True)
    nombre = models.CharField(max_length=100)
    opciones = models.ManyToManyField(
        Opcion, through='CategoriaOpcion', related_name='categorias')
    color = models.CharField(
        max_length=10, default='black', help_text='Color para css (Ej: red o #FF0000)'
    )
    back_color = models.CharField(
        max_length=10, default='white', help_text='Color para css (red o #FF0000)'
    )
    activa = models.BooleanField(
        default=True,
        help_text=(
            'Si no está activa, no se cargan datos '
            'para esta categoria y no se muestran resultados'
        )
    )

    def get_absolute_url(self):
        return reverse('resultados-categoria', args=[self.id])

    def opciones_actuales(self, solo_prioritarias=False):
        """
        Devuelve las opciones asociadas a la categoria en el orden dado
        Determina el orden de la filas a cargar, tal como se definen
        en el acta
        """
        qs = self.opciones.all()
        if solo_prioritarias:
            qs = qs.filter(categoriaopcion__prioritaria=True)
        return qs.distinct().order_by('orden')

    @classmethod
    def para_mesas(cls, mesas):
        """
        Devuelve el conjunto de categorias que son comunes a todas
        las mesas dadas

        Por ejemplo, permite mostrar links válidos a las distintas
        categorias para una sección o circuito.
        Por ejemplo, si filtramos el circuito 1J o cualquiera se sus
        subniveles (escuela, mesa) se debe mostrar la categoria a
        Intentendente de La Matanza, pero no a intendente de San Isidro.
        """
        if isinstance(mesas, QuerySet):
            mesas_count = mesas.count()
        else:
            # si es lista
            mesas_count = len(mesas)

        # el primer filtro devuelve categorias activas que esten
        # relacionadas a una o más mesas, pero no necesariamente a todas
        qs = cls.objects.filter(
            activa=True,
            mesa__in=mesas
        )

        # para garantizar que son categorias asociadas a **todas** las mesas
        # anotamos la cuenta y la comparamos con la cantidad de mesas del conjunto
        qs = qs.annotate(
            num_mesas=Count('mesa')
        ).filter(
            num_mesas=mesas_count
        )
        return qs

    @classmethod
    def actual(cls):
        return cls.objects.first()

    @property
    def electores(self):
        """
        Devuelve la cantidad de electores habilitados para esta categoría
        """
        return Mesa.objects.filter(categorias=self).aggregate(v=Sum('electores'))['v']

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ('id',)

    def __str__(self):
        return self.nombre


class CategoriaOpcion(models.Model):
    categoria = models.ForeignKey('Categoria', on_delete=models.CASCADE)
    opcion = models.ForeignKey('Opcion', on_delete=models.CASCADE)
    prioritaria = models.BooleanField(default=False)

    class Meta:
        unique_together = ('categoria', 'opcion')


class Carga(TimeStampedModel):
    """
    Es el contenedor de la carga de datos de un fiscal
    Define todos los datos comunes (fecha, fiscal, mesa, categoría)
    de una carga, y contiene un conjunto de objetos
    :class:`VotoMesaReportado`
    para las opciones válidas en la mesa-categoría.
    """
    valida = models.BooleanField(null=False, default=True)
    TIPOS = Choices(
        'falta_foto',
        'parcial',
        'total'
    )
    tipo = StatusField(choices_name='TIPOS', null=True, blank=True)
    
    SOURCES = Choices('web', 'csv', 'telegram')
    origen = models.CharField(
        max_length=50, choices=SOURCES, default='web'
    )

    mesa_categoria = models.ForeignKey(
        MesaCategoria, related_name='cargas', on_delete=models.CASCADE
    )
    fiscal = models.ForeignKey('fiscales.Fiscal', null=True, on_delete=models.SET_NULL)
    firma = models.CharField(
        max_length=300, null=True, blank=True, editable=False
    )

    @property
    def mesa(self):
        return self.mesa_categoria.mesa

    @property
    def categoria(self):
        return self.mesa_categoria.categoria

    def actualizar_firma(self):
        """
        a partir del conjunto de reportes de la carga
        se genera una firma como un string
            <id_opcion_A>-<votos_opcion_A>|<id_opcion_B>-<votos_opcion_B>...

        Si esta firma iguala o coincide con la de otras cargas
        se marca consolidada
        """
        tuplas = (
            f'{o}-{v or ""}' for (o, v) in
            self.reportados.values_list(
                'opcion', 'votos'
            ).order_by('opcion__orden')
        )
        self.firma = '|'.join(tuplas)
        self.save(update_fields=['firma'])

    def __str__(self):
        return f'carga de {self.mesa} / {self.categoria} por {self.fiscal}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Genero una novedad.
        NovedadesCarga.objects.create(carga=self)

class NovedadesCarga(TimeStampedModel):
    carga = models.ForeignKey(
        'Carga', null=False, on_delete=models.CASCADE
    )


class VotoMesaReportado(models.Model):
    """
    Representa una "celda" del acta a cargar, es decir, dada una carga
    que define mesa y categoria, existe una instancia de este modelo
    para cada opción y su correspondiente cantidad de votos.
    """
    carga = models.ForeignKey(Carga, related_name='reportados', on_delete=models.CASCADE)
    opcion = models.ForeignKey(Opcion, on_delete=models.CASCADE)

    # es null cuando hay cargas parciales.
    votos = models.PositiveIntegerField(null=True)

    class Meta:
        unique_together = ('carga', 'opcion')

    def __str__(self):
        return f"{self.carga} - {self.opcion}: {self.votos}"


@receiver(post_save, sender=Carga)
def actualizar_categorias_cargadas_para_mesa(sender, instance=None, created=False, **kwargs):
    """
    Actualiza el contador de categorias ya cargadas para una mesa dada.
    Se actualiza cada vez que se guarda una instancia de :class:`Carga`
    """
    mesa = instance.mesa_categoria.mesa
    categorias_cargadas = Carga.objects.filter(
        mesa_categoria__mesa=mesa
    ).values('mesa_categoria__categoria').distinct().count()
    if mesa.cargadas != categorias_cargadas:
        mesa.cargadas = categorias_cargadas
        mesa.save(update_fields=['cargadas'])

@receiver(post_save, sender=MesaCategoria)
def actualizar_categorias_confirmadas_para_mesa(sender, instance=None, created=False, **kwargs):
    """
    Similar a :func:`actualizar_categorias_cargadas_para_mesa`,
    actualiza el contador de categorias ya confirmadas para una mesa dada.
    """
    if instance.status == MesaCategoria.STATUS.total_consolidada_dc:
        mesa = instance.mesa
        confirmadas = MesaCategoria.objects.filter(mesa=mesa, status='total_consolidada_dc').count()
        if mesa.confirmadas != confirmadas:
            mesa.confirmadas = confirmadas
            mesa.save(update_fields=['confirmadas'])


@receiver(post_save, sender=Mesa)
def actualizar_electores(sender, instance=None, created=False, **kwargs):
    """
    Actualiza las denormalizaciones de cantidad de electores a nivel circuito, seccion y distrito
    cada vez que se crea o actualiza una instancia de mesa.

    En general, esto sólo debería ocurrir en la configuración inicial del sistema.
    """
    if (instance.lugar_votacion is not None
        and instance.lugar_votacion.circuito is not None):
        circuito = instance.lugar_votacion.circuito
        seccion = circuito.seccion
        distrito = seccion.distrito

        # circuito
        electores = Mesa.objects.filter(
            lugar_votacion__circuito=circuito,
        ).aggregate(v=Sum('electores'))['v'] or 0
        circuito.electores = electores
        circuito.save(update_fields=['electores'])

        # seccion
        electores = Mesa.objects.filter(
            lugar_votacion__circuito__seccion=seccion,
        ).aggregate(v=Sum('electores'))['v'] or 0
        seccion.electores = electores
        seccion.save(update_fields=['electores'])

        # distrito
        electores = Mesa.objects.filter(
            lugar_votacion__circuito__seccion__distrito=distrito,
        ).aggregate(v=Sum('electores'))['v'] or 0
        distrito.electores = electores
        distrito.save(update_fields=['electores'])
