import logging
from datetime import timedelta
from collections import defaultdict

from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Sum, Count, Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from djgeojson.fields import PointField
from model_utils import Choices
from model_utils.fields import StatusField
from model_utils.models import TimeStampedModel

logger = logging.getLogger("e-va")


class Distrito(models.Model):
    """
    Define el distrito o circunscripción electoral. Es la subdivisión más
    grande en una carta marina. En una elección provincial el distrito es único.

    **Distrito** -> Sección -> Circuito -> Lugar de votación -> Mesa
    """
    numero = models.CharField(null=True, max_length=10)
    nombre = models.CharField(max_length=100)
    electores = models.PositiveIntegerField(default=0)
    prioridad = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(9)])

    class Meta:
        verbose_name = 'Distrito electoral'
        verbose_name_plural = 'Distritos electorales'

    def __str__(self):
        return f"{self.numero} - {self.nombre}"

    def nombre_completo(self):
        return self.nombre


class SeccionPolitica(models.Model):
    """
    Define la sección política, que es una agrupación de nuestras secciones electorales,
    que se usa con fines políticos y para mostrar resultados.

    En términos políticos, en especial para la PBA, nuestra Sección es un Municipio
    (eg, "La Matanza"), y esta sección política es "la tercera sección electoral".

    Distrito -> **Sección política** -> Sección -> Circuito -> Lugar de votación -> Mesa
    """
    distrito = models.ForeignKey(Distrito, on_delete=models.CASCADE, related_name='secciones_politicas')
    numero = models.PositiveIntegerField(null=True)
    nombre = models.CharField(max_length=100)

    class Meta:
        ordering = ('numero', )
        verbose_name = 'Sección política'
        verbose_name_plural = 'Secciones políticas'

    def __str__(self):
        return f"{self.numero} - {self.nombre}"

    def mesas(self, categoria):
        return Mesa.objects.filter(lugar_votacion__circuito__seccion_politica=self, categorias=categoria)

    def nombre_completo(self):
        return f"{self.distrito.nombre_completo()} - {self.nombre}"


class Seccion(models.Model):
    """
    Define la sección electoral:

    Distrito -> **Sección** -> Circuito -> Lugar de votación -> Mesa
    """
    distrito = models.ForeignKey(Distrito, on_delete=models.CASCADE, related_name='secciones')
    seccion_politica = models.ForeignKey(
        SeccionPolitica, null=True, blank=True, on_delete=models.CASCADE, related_name='secciones'
    )
    numero = models.CharField(null=True, max_length=10)
    nombre = models.CharField(max_length=100)
    electores = models.PositiveIntegerField(default=0)
    proyeccion_ponderada = models.BooleanField(
        default=False,
        help_text=(
            'Si está marcado, el cálculo de proyeccion se agrupará '
            'por circuitos para esta sección'
        )
    )
    prioridad = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(9)])

    class Meta:
        ordering = ('numero', )
        verbose_name = 'Sección electoral'
        verbose_name_plural = 'Secciones electorales'

    def resultados_url(self):
        return reverse('resultados-categoria') + f'?seccion={self.id}'

    def __str__(self):
        return f"{self.numero} - {self.nombre}"

    def mesas(self, categoria):
        return Mesa.objects.filter(lugar_votacion__circuito__seccion=self, categorias=categoria)

    def nombre_completo(self):
        if (self.seccion_politica):
            return f"{self.seccion_politica.nombre_completo()} - {self.nombre}"
        else:
            return f"{self.distrito.nombre_completo()} - {self.nombre}"


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
    prioridad = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(9)])

    class Meta:
        verbose_name = 'Circuito electoral'
        verbose_name_plural = 'Circuitos electorales'
        ordering = ('id', )

    def __str__(self):
        return f"{self.numero} - {self.nombre}"

    def resultados_url(self):
        return reverse('resultados-categoria') + f'?circuito={self.id}'

    def mesas(self, categoria):
        """
        Devuelve las mesas asociadas a este circuito para una categoría dada
        """
        return Mesa.objects.filter(lugar_votacion__circuito=self, categorias=categoria)

    def nombre_completo(self):
        return f'{self.seccion.nombre_completo()} - {self.nombre}'


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
    geom = PointField(null=True, blank=True)

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
        return Mesa.objects.filter(lugar_votacion=self, categorias=categoria)

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
        return f'{self.nombre} - {self.circuito}'

    def nombre_completo(self):
        return f'{self.circuito.nombre_completo()}  - {self.nombre}'


class MesaCategoriaQuerySet(models.QuerySet):

    def identificadas(self):
        """
        Filtra instancias que tengan orden de carga definido
        (que se produce cuando hay un primer attachment consolidado).
        """
        return self.filter(orden_de_carga__isnull=False)

    def no_taken(self):
        """
        Filtra que no esté tomada dentro de los últimos
        ``settings.MESA_TAKE_WAIT_TIME`` minutos,
        """
        wait = settings.MESA_TAKE_WAIT_TIME
        desde = timezone.now() - timedelta(minutes=wait)
        return self.filter(
            # No puede estar tomado o tiene que haber expirado el periodo de taken.
            Q(taken__isnull=True) | Q(taken__lt=desde)
        )

    def sin_problemas(self):
        """
        Excluye las instancias que tengan problemas.
        """
        return self.exclude(status=MesaCategoria.STATUS.con_problemas)

    def sin_consolidar_por_doble_carga(self):
        """
        Excluye las instancias no consolidadas con doble carga.
        """
        return self.exclude(status=MesaCategoria.STATUS.total_consolidada_dc)

    def con_carga_pendiente(self):
        return self.identificadas().sin_problemas().no_taken().sin_consolidar_por_doble_carga()

    def siguiente(self):
        """
        Devuelve la siguiente MesaCategoria en orden de prioridad
        de carga.
        """
        return self.con_carga_pendiente().order_by(
            'status', 'categoria__prioridad', 'orden_de_carga', 'mesa__prioridad', 'id'
        ).first()

    def siguiente_de_la_mesa(self, mesa_existente):
        """
        devuelve la siguiente mesacategoria en orden de prioridad
        de carga
        """
        return self.con_carga_pendiente().filter(
            mesa=mesa_existente
        ).order_by('status', 'categoria__prioridad', 'orden_de_carga', 'mesa__prioridad', 'id').first()


class MesaCategoria(models.Model):
    """
    Modelo intermedio para la relación m2m ``Mesa.categorias``
    mantiene el estado de las `cargas`

    Permite guardar el booleano que marca la carga de esa
    "columna" como confirmada.
    """
    objects = MesaCategoriaQuerySet.as_manager()

    STATUS = Choices(
        # no hay cargas
        ('00_sin_cargar', 'sin_cargar', 'sin cargar'),
        # carga parcial única (no csv) o no coincidente
        ('10_parcial_sin_consolidar', 'parcial_sin_consolidar', 'parcial sin consolidar'),
        # no hay dos cargas mínimas coincidentes, pero una es de csv.
        # cargas parcial divergentes sin consolidar
        ('20_parcial_en_conflicto', 'parcial_en_conflicto', 'parcial en conflicto'),
        ('30_parcial_consolidada_csv', 'parcial_consolidada_csv', 'parcial consolidada CSV'),
        # carga parcial consolidada por multicarga
        ('40_parcial_consolidada_dc', 'parcial_consolidada_dc', 'parcial consolidada doble carga'),
        ('50_total_sin_consolidar', 'total_sin_consolidar', 'total sin consolidar'),
        ('60_total_en_conflicto', 'total_en_conflicto', 'total en conflicto'),
        ('70_total_consolidada_csv', 'total_consolidada_csv', 'total consolidada CSV'),
        ('80_total_consolidada_dc', 'total_consolidada_dc', 'total consolidada doble carga'),
        # No siguen en la carga.
        ('90_con_problemas', 'con_problemas', 'con problemas')
    )
    status = StatusField(default=STATUS.sin_cargar)
    mesa = models.ForeignKey('Mesa', on_delete=models.CASCADE)
    categoria = models.ForeignKey('Categoria', on_delete=models.CASCADE)

    # Carga que es representativa del estado actual.
    carga_testigo = models.ForeignKey(
        'Carga', related_name='es_testigo', null=True, blank=True, on_delete=models.SET_NULL
    )

    # timestamp para dar un tiempo de guarda a la espera de una carga
    taken = models.DateTimeField(null=True, editable=False)

    # entero que se define como el procentaje (redondeado) de mesas
    # ya identificadas todavia sin consolidar al momento de identificar la
    # mesa
    orden_de_carga = models.PositiveIntegerField(null=True, blank=True)

    def take(self):
        self.taken = timezone.now()
        self.save(update_fields=['taken'])

    def release(self):
        """
        Libera la mesa, es lo contrario de take().
        """
        self.taken = None
        self.save(update_fields=['taken'])

    def actualizar_orden_de_carga(self):
        """
        Actualiza `self.orden_de_carga` como una proporcion de mesas
        """
        en_circuito = MesaCategoria.objects.filter(
            categoria=self.categoria, mesa__circuito=self.mesa.circuito
        )
        total = en_circuito.count()
        identificadas = en_circuito.identificadas().count()
        self.orden_de_carga = int(round((identificadas + 1) / total, 2) * 100)
        self.save(update_fields=['orden_de_carga'])

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
        verbose_name = 'Mesa categoría'
        verbose_name_plural = "Mesas Categorías"

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
        LugarVotacion,
        verbose_name='Lugar de votacion',
        null=True,
        related_name='mesas',
        on_delete=models.CASCADE
    )
    url = models.URLField(blank=True, help_text='url al telegrama')
    electores = models.PositiveIntegerField(null=True, blank=True)
    prioridad = models.PositiveIntegerField(default=0)

    def categoria_add(self, categoria):
        MesaCategoria.objects.get_or_create(mesa=self, categoria=categoria)

    @classmethod
    def obtener_mesa_en_circuito_seccion_distrito(cls, mesa, circuito, seccion, distrito):
        """
        Valida si existe una mesa con dicho codigo en el circuito y seccion indicados
        """
        qs = cls.objects.filter(
            numero=mesa,
            circuito__numero=circuito,
            circuito__seccion__numero=seccion,
            circuito__seccion__distrito__numero=distrito
        )
        return qs.get()

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
        for i, a in enumerate(self.attachments.filter(status='identificada').order_by('modified'), 1):
            if a.foto_edited:
                fotos.append((f'Foto {i} (editada)', a.foto_edited))
            fotos.append((f'Foto {i} (original)', a.foto))
        return fotos

    def metadata(self):
        """
        Las opciones metadatas comunes a las distintas categorías de la misma mesa
        reúsan el valor reportado. Se cargan hasta que se consolide en alguna categoría
        y las siguientes cargas reusarán sus valores reportados.

        Este método devuelve la lista de tuplas de (opción metadata, número)
        para alguna de las cargas consolidadas testigo de la mesa. El número
        es la cantidad de "votos".
        """
        return VotoMesaReportado.objects.filter(
            opcion__tipo=Opcion.TIPOS.metadata,
            carga__mesa_categoria__mesa=self,
            carga__mesa_categoria__status=MesaCategoria.STATUS.total_consolidada_dc
        ).distinct().values_list('opcion', 'votos')

    def __str__(self):
        # return f'nro {self.numero} - circ. {self.circuito}'
        return f'{self.numero}'

    def nombre_completo(self):
        return self.lugar_votacion.nombre_completo() + " - " + self.numero


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
    pero actualmente sus votos se computan agregados.

    """
    # Tipos positivos son las opciones contables (asociadas a partidos).
    # Tipos no positivos son blanco, nulos, etc
    # Metada son campos extras como "total de votos", "total de sobres", etc.
    # que son únicos por mesa (no están en cada categoría).
    TIPOS = Choices('positivo', 'no_positivo', 'metadata')
    tipo = models.CharField(max_length=100, choices=TIPOS, default=TIPOS.positivo)

    nombre = models.CharField(max_length=100)
    nombre_corto = models.CharField(max_length=20, default='')
    # El código de opción corresponde con el nro de lista en los archivos CSV.
    codigo = models.CharField(max_length=10, help_text='Codigo de opción', null=True, blank=True)
    partido = models.ForeignKey(
        Partido, null=True, on_delete=models.SET_NULL, blank=True, related_name='opciones'
    )  # blanco, / recurrido / etc
    orden = models.PositiveIntegerField(help_text='Orden en la boleta', null=True, blank=True)

    codigo_dne = models.PositiveIntegerField(
        null=True, blank=True, help_text='Nº asignado en la base de datos de resultados oficiales'
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
            return f'{self.partido.codigo} - {self.nombre}'  # {self.partido.nombre_corto}
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
    # Se usan para referencia en otros lugares, no aquí.
    NIVELES_AGREGACION = Choices(
        'distrito', 'seccion_politica', 'seccion', 'circuito', 'lugar_de_votacion', 'mesa'
    )

    def __str__(self):
        return f'{self.nombre}'

    class Meta:
        verbose_name = 'Elección'
        verbose_name_plural = 'Elecciones'


class Categoria(models.Model):
    """
    Representa una categoría electiva, es decir, una "columna" del acta.
    Por ejemplo: Presidente y Vicepresidente, Intendente de La Matanza, etc)

    Una categoría tiene habilitadas diferentes :py:meth:`opciones <Opcion>`
    que incluyen las partidarias (boletas) y blanco, nulo, etc.
    """
    eleccion = models.ForeignKey(Eleccion, null=True, on_delete=models.SET_NULL)
    slug = models.SlugField(max_length=100, unique=True)
    nombre = models.CharField(max_length=100)
    opciones = models.ManyToManyField(Opcion, through='CategoriaOpcion', related_name='categorias')
    color = models.CharField(max_length=10, default='black', help_text='Color para CSS (ej, red o #FF0000)')
    back_color = models.CharField(
        max_length=10, default='white', help_text='Color para CSS (ej, red o #FF0000)'
    )
    activa = models.BooleanField(
        default=True,
        help_text=(
            'Si no está activa, no se cargan datos '
            'para esta categoría y no se muestran resultados.'
        )
    )

    requiere_cargas_parciales = models.BooleanField(default=False)
    prioridad = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(9)])

    def get_opcion_blancos(self):
        return self.opciones.get(**settings.OPCION_BLANCOS)

    def get_opcion_total_votos(self):
        return self.opciones.get(**settings.OPCION_TOTAL_VOTOS)

    def get_opcion_total_sobres(self):
        return self.opciones.get(**settings.OPCION_TOTAL_SOBRES)

    def get_absolute_url(self):
        return reverse('resultados-categoria', args=[self.id])

    def opciones_actuales(self, solo_prioritarias=False):
        """
        Devuelve las opciones asociadas a la categoría en el orden dado
        Determina el orden de la filas a cargar, tal como se definen
        en el acta.
        """
        qs = self.opciones.all()
        if solo_prioritarias:
            qs = qs.filter(categoriaopcion__prioritaria=True)
        return qs.distinct().order_by('orden')

    @classmethod
    def para_mesas(cls, mesas):
        """
        Devuelve el conjunto de categorías que son comunes a todas
        las mesas dadas.

        Por ejemplo, permite mostrar links válidos a las distintas
        categorías para una sección o circuito.
        Por ejemplo, si filtramos el circuito 1J o cualquiera se sus
        subniveles (escuela, mesa) se debe mostrar la categoría a
        Intentendente de La Matanza, pero no a intendente de San Isidro.
        """
        if isinstance(mesas, models.QuerySet):
            mesas_count = mesas.count()
        else:
            # si es lista
            mesas_count = len(mesas)

        # El primer filtro devuelve categorías activas que esten
        # relacionadas a una o más mesas, pero no necesariamente a todas
        qs = cls.objects.filter(activa=True, mesa__in=mesas)

        # Para garantizar que son categorías asociadas a **todas** las mesas
        # anotamos la cuenta y la comparamos con la cantidad de mesas del conjunto
        qs = qs.annotate(num_mesas=Count('mesa')).filter(num_mesas=mesas_count)
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
        ordering = ('id', )

    def __str__(self):
        return self.nombre


class CategoriaOpcion(models.Model):
    categoria = models.ForeignKey('Categoria', on_delete=models.CASCADE)
    opcion = models.ForeignKey('Opcion', on_delete=models.CASCADE)
    prioritaria = models.BooleanField(default=False)

    class Meta:
        unique_together = ('categoria', 'opcion')
        verbose_name = 'Asociación Categoría-Opción'
        verbose_name_plural = 'Asociaciones Categoría-Opción'
        ordering = ['categoria']

    def __str__(self):
        prioritaria = ' (es prioritaria)' if self.prioritaria else ''
        return f'{self.categoria} - {self.opcion} {prioritaria}'


class Carga(TimeStampedModel):
    """
    Es el contenedor de la carga de datos de un fiscal
    Define todos los datos comunes (fecha, fiscal, mesa, categoría)
    de una carga, y contiene un conjunto de objetos
    :class:`VotoMesaReportado`
    para las opciones válidas en la mesa-categoría.
    """
    invalidada = models.BooleanField(null=False, default=False)
    TIPOS = Choices(
        'problema',
        'parcial',
        'total'
    )
    tipo = models.CharField(max_length=50, choices=TIPOS)

    SOURCES = Choices('web', 'csv', 'telegram')
    origen = models.CharField(max_length=50, choices=SOURCES, default='web')

    mesa_categoria = models.ForeignKey(MesaCategoria, related_name='cargas', on_delete=models.CASCADE)
    fiscal = models.ForeignKey('fiscales.Fiscal', null=True, on_delete=models.SET_NULL)
    firma = models.CharField(max_length=300, null=True, blank=True, editable=False)
    procesada = models.BooleanField(default=False)

    @property
    def mesa(self):
        return self.mesa_categoria.mesa

    def invalidar(self):
        self.invalidada = True
        self.procesada = False
        self.save(update_fields=['invalidada', 'procesada'])

    @property
    def categoria(self):
        return self.mesa_categoria.categoria

    def actualizar_firma(self, forzar=False):
        """
        A partir del conjunto de reportes de la carga
        se genera una firma como un string
            <id_opcion_A>-<votos_opcion_A>|<id_opcion_B>-<votos_opcion_B>...

        Si esta firma iguala o coincide con la de otras cargas
        se marca consolidada.
        """
        # Si ya hay firma y no están forzando, listo.
        if self.firma and not forzar:
            return
        tuplas = (f'{o}-{v or ""}' for (o, v) in self.opcion_votos().order_by('opcion__orden'))
        self.firma = '|'.join(tuplas)
        self.save(update_fields=['firma'])

    def opcion_votos(self):
        """ Devuelve una lista de los votos para cada opción. """
        return self.reportados.values_list('opcion', 'votos')

    def __str__(self):
        str_invalidada = ' (invalidada) ' if self.invalidada else ' '
        return f'carga{str_invalidada}de {self.mesa} / {self.categoria} por {self.fiscal}'


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


class TecnicaProyeccion(models.Model):
    """
    Representa una estrategia para agrupar circuitos para hacer proyecciones.
    Contiene una lista de AgrupacionCircuitos que debería en total cubrir a todos los circuitos
    correspondientes a la categoria que se desea proyectar.
    """
    nombre = models.CharField(max_length=100)

    class Meta:
        ordering = ('nombre', )
        verbose_name = 'Técnica de Proyección'
        verbose_name_plural = 'Técnicas de Proyección'

    def __str__(self):
        return f'Técnica de proyección {self.nombre}'


class AgrupacionCircuitos(models.Model):
    """
    Representa un conjunto de circuitos que se computarán juntos a los efectos de una proyección.
    """
    nombre = models.CharField(max_length=100)
    proyeccion = models.ForeignKey(TecnicaProyeccion, on_delete=models.CASCADE, related_name='agrupaciones')
    minimo_mesas = models.PositiveIntegerField(default=1)
    circuitos = models.ManyToManyField(Circuito, related_name='agrupaciones')

    class Meta:
        verbose_name = 'Agrupación de Circuitos'
        verbose_name_plural = 'Agrupaciones de Cicuitos'

    def __str__(self):
        return f'Agrupación de circuitos {self.nombre}'


@receiver(post_save, sender=Mesa)
def actualizar_electores(sender, instance=None, created=False, **kwargs):
    """
    Actualiza las denormalizaciones de cantidad de electores a nivel circuito, seccion y distrito
    cada vez que se crea o actualiza una instancia de mesa.

    En general, esto sólo debería ocurrir en la configuración inicial del sistema.
    """
    if (instance.lugar_votacion is not None and instance.lugar_votacion.circuito is not None):

        circuito = instance.lugar_votacion.circuito
        seccion = circuito.seccion
        distrito = seccion.distrito

        # circuito
        electores = Mesa.objects.filter(lugar_votacion__circuito=circuito, ).aggregate(v=Sum('electores')
                                                                                       )['v'] or 0
        circuito.electores = electores
        circuito.save(update_fields=['electores'])

        # seccion
        electores = Mesa.objects.filter(lugar_votacion__circuito__seccion=seccion, ).aggregate(
            v=Sum('electores')
        )['v'] or 0
        seccion.electores = electores
        seccion.save(update_fields=['electores'])

        # distrito
        electores = Mesa.objects.filter(lugar_votacion__circuito__seccion__distrito=distrito, ).aggregate(
            v=Sum('electores')
        )['v'] or 0
        distrito.electores = electores
        distrito.save(update_fields=['electores'])
