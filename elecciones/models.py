import math
from datetime import timedelta
from collections import defaultdict

from django.dispatch import receiver
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Sum, Count, Q, F
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from djgeojson.fields import PointField
from model_utils import Choices, FieldTracker
from model_utils.fields import StatusField
from model_utils.models import TimeStampedModel
from constance import config
import structlog

logger = structlog.get_logger(__name__)

MAX_INT_DB = 2147483647

TIPOS_DE_AGREGACIONES = Choices(
    ('todas_las_cargas', 'Todas'),
    ('solo_consolidados', 'Consolidadas'),
    ('solo_consolidados_doble_carga', 'Consolidadas con doble Carga'),
)

OPCIONES_A_CONSIDERAR = Choices(
    ('prioritarias', 'Prioritarias'),
    ('todas', 'Todas'),
)

NIVELES_DE_AGREGACION = Choices(
    ('distrito', 'Provincia'),
    ('seccion_politica', 'Sección Política'),
    ('seccion', 'Sección Electoral'),
    ('circuito', 'Circuito'),
    ('lugar_de_votacion', 'Lugar de Votación'),
    ('mesa', 'Mesa'),
)

NIVELES_AGREGACION = [x[0] for x in NIVELES_DE_AGREGACION]


def canonizar(valor):
    """
    Tomado prestado de adjuntos/csv_import, también está en managament/commands
    Pasa a mayúsculas y elimina espacios.
    Si se trata de un número, elimina los ceros previos.
    """
    if valor is None:
        return valor
    if not isinstance(valor, str):
        return valor
    valor = valor.upper().strip()
    if valor.isdigit():
        valor = str(int(valor))  # Esto elimina ceros y lo volvemos a string
    return valor


class DistritoManager(models.Manager):
    def get_by_natural_key(self, numero):
        return self.get(numero = numero)


class Distrito(models.Model):
    """
    Define el distrito o circunscripción electoral. Es la subdivisión más
    grande en una carta marina. En una elección provincial el distrito es único.

    **Distrito** -> Sección -> Circuito -> Lugar de votación -> Mesa
    """
    numero = models.CharField(null=True, max_length=10, db_index=True)
    nombre = models.CharField(max_length=100)
    electores = models.PositiveIntegerField(default=0)
    prioridad = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(9)])

    objects = DistritoManager()

    class Meta:
        verbose_name = 'Distrito electoral'
        verbose_name_plural = 'Distritos electorales'

    def __str__(self):
        return f"{self.numero} - {self.nombre}"

    def nombre_completo(self):
        return self.nombre

    def natural_key(self):
        return (self.numero, )


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
        ordering = ('numero',)
        verbose_name = 'Sección política'
        verbose_name_plural = 'Secciones políticas'

    def __str__(self):
        return f"{self.numero} - {self.nombre}"

    def mesas(self, categoria):
        return Mesa.objects.filter(lugar_votacion__circuito__seccion_politica=self, categorias=categoria)

    def nombre_completo(self):
        return f"{self.distrito.nombre_completo()} - {self.nombre}"


class SeccionManager(models.Manager):
    def get_by_natural_key(self, distrito, numero):
        return self.get(distrito__numero = distrito, numero = numero)


class Seccion(models.Model):
    """
    Define la sección electoral:

    Distrito -> **Sección** -> Circuito -> Lugar de votación -> Mesa
    """
    distrito = models.ForeignKey(Distrito, on_delete=models.CASCADE, related_name='secciones')
    seccion_politica = models.ForeignKey(
        SeccionPolitica, null=True, blank=True, on_delete=models.CASCADE, related_name='secciones'
    )
    numero = models.CharField(null=True, max_length=10, db_index=True)
    nombre = models.CharField(max_length=100)
    electores = models.PositiveIntegerField(default=0)
    # esta es la prioridad del "viejo" modelo de scheduling, está deprecada a la espera del refactor
    # que permita borrarla
    prioridad = models.PositiveIntegerField(
        default=0, null=True, blank=True, validators=[MaxValueValidator(1000)])
    # estos son los nuevos atributos que intervienen en el modelo actual de scheduling
    prioridad_hasta_2 = models.PositiveIntegerField(
        default=None, null=True, blank=True, validators=[MaxValueValidator(1000000), MinValueValidator(1)]
    )
    prioridad_2_a_10 = models.PositiveIntegerField(
        default=None, null=True, blank=True, validators=[MaxValueValidator(1000000), MinValueValidator(1)]
    )
    prioridad_10_a_100 = models.PositiveIntegerField(
        default=None, null=True, blank=True, validators=[MaxValueValidator(1000000), MinValueValidator(1)]
    )
    cantidad_minima_prioridad_hasta_2 = models.PositiveIntegerField(
        default=None, null=True, blank=True, validators=[MaxValueValidator(1000), MinValueValidator(1)]
    )

    # Tracker de cambios en los atributos relacionados con la prioridad,
    # usado en la función que dispara en el post_save
    tracker = FieldTracker(
        fields=[
            'prioridad_hasta_2',
            'cantidad_minima_prioridad_hasta_2',
            'prioridad_2_a_10',
            'prioridad_10_a_100'
        ]
    )

    objects = SeccionManager()

    class Meta:
        ordering = ('numero',)
        verbose_name = 'Sección electoral'
        verbose_name_plural = 'Secciones electorales'

    def resultados_url(self):
        return reverse('resultados-primera-categoria') + f'?seccion={self.id}'

    def __str__(self):
        return f"{self.numero} - {self.nombre}"

    def mesas(self, categoria):
        return Mesa.objects.filter(lugar_votacion__circuito__seccion=self, categorias=categoria)

    def nombre_completo(self):
        if (self.seccion_politica):
            return f"{self.seccion_politica.nombre_completo()} - {self.nombre}"
        else:
            return f"{self.distrito.nombre_completo()} - {self.nombre}"

    def natural_key(self):
        return self.distrito.natural_key() + (self.numero, ) 
    natural_key.dependencies = ['elecciones.distrito']

class Circuito(models.Model):
    """
    Define el circuito, perteneciente a una sección

    Distrito -> Sección -> **Circuito** -> Lugar de votación -> Mesa
    """
    seccion = models.ForeignKey(Seccion, related_name='circuitos', on_delete=models.CASCADE)
    localidad_cabecera = models.CharField(max_length=100, null=True, blank=True)

    numero = models.CharField(max_length=10, db_index=True)
    nombre = models.CharField(max_length=100)
    electores = models.PositiveIntegerField(default=0)
    prioridad = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(9)])

    class Meta:
        verbose_name = 'Circuito electoral'
        verbose_name_plural = 'Circuitos electorales'
        ordering = ('id',)

    def __str__(self):
        return f"{self.numero} - {self.nombre}"

    def resultados_url(self):
        return reverse('resultados-primera-categoria') + f'?circuito={self.id}'

    def mesas(self, categoria):
        """
        Devuelve las mesas asociadas a este circuito para una categoría dada
        """
        return Mesa.objects.filter(lugar_votacion__circuito=self, categorias=categoria)

    def nombre_completo(self):
        return f'{self.seccion.nombre_completo()} - {self.nombre}'

    @property
    def distrito(self):
        return self.seccion.distrito


class LugarVotacion(models.Model):
    """
    Define el lugar de votación (escuela) que pertenece a un circuito
    y contiene mesas.
    Tiene un representación geoespacial (point).

    Distrito -> Sección -> Circuito -> **Lugar de votación** -> Mesa
    """

    circuito = models.ForeignKey(Circuito, related_name='lugares_votacion', on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=100)
    barrio = models.CharField(max_length=100, blank=True)
    ciudad = models.CharField(max_length=100, blank=True)
    numero = models.CharField(max_length=10, help_text='Número de escuela', null=True, blank=True)

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

    @property
    def distrito(self):
        return self.circuito.seccion.distrito


class MesaCategoriaQuerySet(models.QuerySet):
    campos_de_orden = [
        'cant_fiscales_asignados_redondeados',  # Primero las que tienen menos gente trabajando en ellas.
        'prioridad_status', 'orden_de_carga',
        'cant_asignaciones_realizadas_redondeadas',  # En caso de empate no damos siempre la de menor id.
        'id',
    ]

    def identificadas(self):
        """
        Filtra instancias que tengan orden de carga definido
        (que se produce cuando hay un primer attachment consolidado).
        """
        # Si bien parece redundante chequear orden de carga y attachment preferimos
        # estar seguros de que no se cuele una mesa sin foto.
        return self.filter(orden_de_carga__isnull=False).exclude(mesa__attachments=None)

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

    def sin_consolidar_por_csv(self):
        """
        Excluye las instancias no consolidadas con doble carga.
        """
        return self.exclude(status=MesaCategoria.STATUS.total_consolidada_csv)

    def sin_cargas_del_fiscal(self, fiscal):
        """
        Excluye las instancias que tengan alguna carga del fiscal indicado
        """
        return self.exclude(cargas__fiscal=fiscal)

    def con_carga_pendiente(self, for_update=True):
        qs = self.select_for_update(skip_locked=True) if for_update else self
        return qs.identificadas().sin_problemas().sin_consolidar_por_doble_carga()

    def anotar_prioridad_status(self):
        """
        Dados los status posibles anota el querset
        ``prioridad_status`` con un valor entero (0, 1, 2, ...)
        que se corresponde con el índice del status en la constante
        ``config.PRIORIDAD_STATUS``, que es configurable vía Constance.
        Sirve para poder ordenar por "prioridad de status"::

            >>> qs.anotar_prioridad_status().order_by('prioridad_status')

        Por defecto, esta prioridad sale del orden definido
        en ``settings.MC_STATUS_CHOICE``.
        """
        whens = []
        for valor, status in enumerate(config.PRIORIDAD_STATUS.split()):
            whens.append(models.When(status=status, then=models.Value(valor)))
        return self.annotate(
            prioridad_status=models.Case(
                *whens,
                output_field=models.IntegerField(),
            )
        )

    def redondear_cant_fiscales_asignados_y_de_asignaciones(self):
        """
        Redondea la cantidad de fiscales asignados y de asignaciones a múltiplos de 
        ``settings.MIN_COINCIDENCIAS_CARGAS`` para que al asignar mesas
        no se pospongan indefinidamente mesas que fueron entregadas ya a algún
        fiscal.
        """
        return self.annotate(
            cant_fiscales_asignados_redondeados=F(
                'cant_fiscales_asignados') / settings.MIN_COINCIDENCIAS_CARGAS,
            cant_asignaciones_realizadas_redondeadas=F(
                'cant_asignaciones_realizadas') / 
                (config.MULTIPLICADOR_CANT_ASIGNACIONES_REALIZADAS * settings.MIN_COINCIDENCIAS_CARGAS),
        )

    def ordenadas_por_prioridad(self):
        return self.anotar_prioridad_status().redondear_cant_fiscales_asignados_y_de_asignaciones().order_by(
            *self.campos_de_orden
        )

    def debug_mas_prioritaria(self):
        """
        Esta función invoca a ordenadas_por_prioridad() y además imprime los campos de orden.
        Sirve sólo para debuggear.
        """
        return self.ordenadas_por_prioridad().values(
            *self.campos_de_orden
        )

    def mas_prioritaria(self):
        """
        Devuelve la intancia más prioritaria del queryset.
        """
        return self.ordenadas_por_prioridad().first()

    def siguiente(self):
        """
        Devuelve mesacat con carga pendiente más prioritaria
        """
        return self.con_carga_pendiente().mas_prioritaria()

    def siguiente_para_ub(self):
        """
        Devuelve mesacat con carga pendiente más prioritaria
        """
        return self.con_carga_pendiente().sin_consolidar_por_csv().mas_prioritaria()


class MesaCategoria(models.Model):
    """
    Modelo intermedio para la relación m2m ``Mesa.categorias``
    mantiene el estado de las `cargas`
    """
    objects = MesaCategoriaQuerySet.as_manager()

    STATUS = settings.MC_STATUS_CHOICE

    status = StatusField(default=STATUS.sin_cargar)
    mesa = models.ForeignKey('Mesa', on_delete=models.CASCADE)
    categoria = models.ForeignKey('Categoria', on_delete=models.CASCADE)

    # Carga que es representativa del estado actual.
    carga_testigo = models.ForeignKey(
        'Carga', related_name='es_testigo', null=True, blank=True, on_delete=models.SET_NULL
    )

    carga_oficial = models.ForeignKey(
        'Carga', related_name='es_oficial', null=True, blank=True, on_delete=models.SET_NULL
    )

    parcial_oficial = models.ForeignKey(
        'Carga', related_name='es_parcial_oficial', null=True, blank=True, on_delete=models.SET_NULL
    )

    # Entero que se define como el procentaje (redondeado) de mesas del circuito
    # ya identificadas al momento de identificar la mesa.
    # Incide en el cálculo del orden_de_carga.
    percentil = models.PositiveIntegerField(null=True, blank=True)

    # En qué orden se identificó esta MesaCategoría dentro de las del circuito.
    # Incide en el cálculo del orden_de_carga.
    # aumenta en forma correlativa, salvo colisiones que no perjudican al uso en una medida relevante.
    orden_de_llegada = models.PositiveIntegerField(null=True, blank=True)

    # Orden relativo de carga, usado en la prioritización.
    orden_de_carga = models.PositiveIntegerField(null=True, blank=True)

    # Registra a cuántos fiscales se les entregó la mesa para que trabajen en ella.
    cant_fiscales_asignados = models.PositiveIntegerField(
        default=0,
        blank=False,
        null=False
    )

    # Este otro contador, en cambio, registra cuántas veces fue entregado un attachment
    # a algún fiscal. Su objetivo es desempatar y hacer que en caso de que todos los demás
    # parámetros de prioridad sea iguales (por ejemplo, muchas mesa-categorías sin cargar, de una
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
        logger.info('mc asignada', id=self.id)

    def desasignar_a_fiscal(self):
        # Si por error alguien hizo un submit de más, no es un problema, por eso se redondea a cero.
        self.cant_fiscales_asignados = max(0, self.cant_fiscales_asignados - 1)
        self.save(update_fields=['cant_fiscales_asignados'])
        logger.info('mc desasignada', id=self.id)

    def actualizar_orden_de_carga(self):
        """
        Actualiza `self.orden_de_carga` a partir de las prioridades por seccion y categoria
        """
        # evitar import circular
        from scheduling.models import mapa_prioridades_para_mesa_categoria

        en_circuito = MesaCategoria.objects.filter(
            categoria=self.categoria, mesa__circuito=self.mesa.circuito
        )
        total = en_circuito.count()
        identificadas = en_circuito.identificadas().count()

        self.orden_de_llegada = identificadas + 1
        self.percentil = math.floor((identificadas * 100) / total) + 1
        self.recalcular_orden_de_carga()
        logger.info(
            'actualizar orden',
            id=self.id,
            coef=self.orden_de_carga,
            llegada=self.orden_de_llegada,
            p=self.percentil
        )
        self.save(update_fields=['orden_de_carga', 'orden_de_llegada', 'percentil'])

    def recalcular_orden_de_carga(self):
        """
        Actualiza el valor de `self.orden_de_carga` a partir de las prioridades por sección y categoría,
        **sin** disparar el `save` correspondiente.
        """
        # evitar import circular
        from scheduling.models import mapa_prioridades_para_mesa_categoria

        prioridades = mapa_prioridades_para_mesa_categoria(self)
        valor_para = prioridades.valor_para(self.percentil - 1, self.orden_de_llegada)
        self.orden_de_carga = min(valor_para * self.percentil, MAX_INT_DB)

    def invalidar_cargas(self):
        """
        Por alguna razón, hay que marcar todas las cargas que se hicieron para esta MesaCategoria
        como inválidas.
        """
        for carga in self.cargas.all():
            carga.invalidar()

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

    def datos_previos(self, tipo_carga):
        """
        Devuelve un diccionario que contiene informacion confirmada
        (proveniente de campos de metadata o prioritarios compartidos)
        para "pre completar" una carga.

            {opcion.id: cantidad_votos, ...}

        Si una opcion está en este diccionario, su campo votos
        se inicilizará con la cantidad de votos y será de sólo lectura,
        validando además que coincidan cuando la carga se guarda.
        """
        datos = dict(self.mesa.metadata())
        if tipo_carga == 'total' and self.status == MesaCategoria.STATUS.parcial_consolidada_dc:
            # una carga total con parcial consolidada reutiliza los datos ya cargados
            datos.update(
                dict(self.carga_testigo.opcion_votos())
            )
        return datos

    class Meta:
        unique_together = ('mesa', 'categoria')
        verbose_name = 'Mesa categoría'
        verbose_name_plural = "Mesas Categorías"

    def actualizar_status(self, status, carga_testigo):
        self.status = status
        self.carga_testigo = carga_testigo
        logger.info('mc status', id=self.id, status=status, testigo=getattr(carga_testigo, 'id', None))
        self.save(update_fields=['status', 'carga_testigo'])

    def actualizar_parcial_oficial(self, parcial_oficial):
        self.parcial_oficial = parcial_oficial
        self.save(update_fields=['parcial_oficial'])

    @classmethod
    def recalcular_orden_de_carga_para_categoria(cls, categoria):
        """
        Recalcula el orden_de_carga de las MesaCategoria correspondientes a la categoría indicada
        que estén pendientes de carga.
        Se usa como acción derivada del cambio de prioridades en la categoría.
        """
        mesa_cats_a_actualizar = cls.objects.identificadas().sin_problemas() \
            .sin_consolidar_por_doble_carga().filter(categoria=categoria)
        cls.recalcular_orden_de_carga_mesas(mesa_cats_a_actualizar)

    @classmethod
    def recalcular_orden_de_carga_para_seccion(cls, seccion):
        """
        Recalcula el orden_de_carga de las MesaCategoria correspondientes a la sección indicada
        que estén pendientes de carga.
        Se usa como acción derivada del cambio de prioridades en la categoría.
        """
        mesa_cats_a_actualizar = cls.objects.identificadas().sin_problemas() \
            .sin_consolidar_por_doble_carga().filter(mesa__circuito__seccion=seccion)
        cls.recalcular_orden_de_carga_mesas(mesa_cats_a_actualizar)

    @classmethod
    def recalcular_orden_de_carga_mesas(cls, mesa_cats):
        for mesa_cat in mesa_cats:
            mesa_cat.recalcular_orden_de_carga()
        cls.objects.bulk_update(mesa_cats, ['orden_de_carga'])


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
    circuito = models.ForeignKey(Circuito, null=True, related_name='mesas', on_delete=models.SET_NULL)
    lugar_votacion = models.ForeignKey(
        LugarVotacion,
        verbose_name='Lugar de votacion',
        # Durante el escrutinio queremos poder crear mesas en caliente
        # y tal vez no sepamos el lugar de votación.
        null=True, blank=True, default=None,
        related_name='mesas',
        on_delete=models.CASCADE
    )
    url = models.URLField(blank=True, help_text='url al telegrama')
    electores = models.PositiveIntegerField(null=True, blank=True)
    prioridad = models.PositiveIntegerField(default=0)
    extranjeros = models.BooleanField(default=False)

    class Meta:
        unique_together = ('circuito', 'numero')

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

    def invalidar_asignacion_attachment(self):
        """
        Efecto de que esta mesa tenía un attachment asociado y ya no lo tiene.
        Hay que: invalidar todas las cargas, y borrar el orden de carga de las MesaCategoria
        para que no se tengan en cuenta en el scheduling
        """
        logger.info('invalidar asignacion attachment', mesa=self.id)
        for mc in MesaCategoria.objects.filter(mesa=self):
            mc.orden_de_carga = None
            mc.percentil = None
            mc.orden_de_llegada = None
            mc.save(update_fields=['orden_de_carga', 'percentil', 'orden_de_llegada'])
            mc.invalidar_cargas()

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
        return self.lugar_votacion.nombre_completo() + " - Mesa N°" + self.numero

    @property
    def distrito(self):
        return self.circuito.seccion.distrito


class Partido(models.Model):
    """
    Representa un partido político o alianza, que contiene :py:class:`opciones <Opcion>`.
    """
    orden = models.PositiveIntegerField(help_text='Orden opcion')
    numero = models.PositiveIntegerField(null=True, blank=True)
    codigo = models.CharField(max_length=10, help_text='Codigo de partido', null=True, blank=True, db_index=True)
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
    # Dado que muchas veces la justicia no le pone un código a las "sub listas"
    # en las PASO, se termina sintentizando y podría ser largo.
    codigo = models.CharField(
        max_length=30, help_text='Codigo de opción', null=True, blank=True,
        db_index=True
    )
    partido = models.ForeignKey(
        Partido, null=True, on_delete=models.SET_NULL, blank=True, related_name='opciones'
    )  # blanco, / recurrido / etc

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

    @classmethod
    def opciones_no_partidarias(cls):
        return ['OPCION_BLANCOS', 'OPCION_TOTAL_VOTOS', 'OPCION_TOTAL_SOBRES', 'OPCION_NULOS']

    @classmethod
    def blancos(cls):
        return cls.objects.get(**settings.OPCION_BLANCOS)

    @classmethod
    def total_votos(cls):
        return cls.objects.get(**settings.OPCION_TOTAL_VOTOS)

    @classmethod
    def nulos(cls):
        return cls.objects.get(**settings.OPCION_NULOS)

    @classmethod
    def sobres(cls):
        return cls.objects.get(**settings.OPCION_TOTAL_SOBRES)

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

    def __str__(self):
        return f'{self.nombre}'

    class Meta:
        verbose_name = 'Elección'
        verbose_name_plural = 'Elecciones'

class CategoriaGeneral(models.Model):
    """
    A diferencia del modelo `Categoria`, éste representa una categoría sin
    asociación geográfica. Por ejemplo "Intendente", sin decir de dónde.

    Sirve para poder de alguna manera agrupar a todas las categorías "Intendende de X",
    además de para permitir meter aquí atributos de visualización comunes a ellas, así
    como también nombres de columnas en, por ejemplo, el CSV.
    """
    eleccion = models.ForeignKey(Eleccion, null=True, on_delete=models.SET_NULL)
    slug = models.SlugField(max_length=100, unique=True)
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre

class Categoria(models.Model):
    """
    Representa una categoría electiva, es decir, una "columna" del acta.
    Por ejemplo: Presidente y Vicepresidente, Intendente de La Matanza, etc)

    Una categoría tiene habilitadas diferentes :py:meth:`opciones <Opcion>`
    que incluyen las partidarias (boletas) y blanco, nulo, etc.
    """
    eleccion = models.ForeignKey(Eleccion, null=True, on_delete=models.SET_NULL)
    categoria_general = models.ForeignKey(CategoriaGeneral, null=False,
        on_delete=models.SET_NULL, related_name='categorias'
    )
    # Información geográfica para anclar una categoría a una provincia o municipio.
    distrito = models.ForeignKey(
        'elecciones.Distrito', on_delete=models.SET_NULL, null=True, blank=True,
    )
    seccion = models.ForeignKey(
        'elecciones.Seccion', null=True, blank=True, on_delete=models.SET_NULL
    )

    slug = models.SlugField(max_length=100, unique=True)
    nombre = models.CharField(max_length=100, db_index=True)
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

    sensible = models.BooleanField(
        default=False,
        help_text=(
            'Solo pueden visualizar los resultados de esta cagtegoría con permisos especiales.'
        )
    )

    requiere_cargas_parciales = models.BooleanField(default=False)
    prioridad = models.PositiveIntegerField(
        default=None, null=True, blank=True, validators=[MaxValueValidator(1000000), MinValueValidator(1)])

    # Tracker de cambios en el atributo prioridad, usado en la función que dispara en el post_save
    tracker = FieldTracker(fields=['prioridad'])

    def get_absolute_url(self):
        return reverse('resultados-categoria', args=[self.id])

    def get_url_avance_de_carga(self):
        return reverse('avance-carga', args=[self.id])

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
        ordering = ('id',)

    def __str__(self):
        return self.nombre


class CategoriaOpcion(models.Model):
    categoria = models.ForeignKey('Categoria', on_delete=models.CASCADE)
    opcion = models.ForeignKey('Opcion', on_delete=models.CASCADE)
    orden = models.PositiveIntegerField(help_text='Orden en el acta', null=True, blank=True)
    prioritaria = models.BooleanField(default=False)

    class Meta:
        unique_together = ('categoria', 'opcion')
        verbose_name = 'Asociación Categoría-Opción'
        verbose_name_plural = 'Asociaciones Categoría-Opción'
        ordering = ['categoria']

    def __str__(self):
        prioritaria = ' (es prioritaria)' if self.prioritaria else ''
        return f'{self.categoria} - {self.opcion} {prioritaria}'

    def set_prioritaria(self):
        self.prioritaria = True
        logger.info('set prioritaria', id=self.id)
        self.save(update_fields=['prioritaria'])


class CargasIncompatiblesError(Exception):
    """
    Error que se produce si se pide la resta entre dos cargas incompatibles
    """
    pass


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
        'total',
        'total_oficial',
        'parcial_oficial'
    )
    tipo = models.CharField(max_length=50, choices=TIPOS)

    SOURCES = Choices('web', 'csv', 'telegram')
    origen = models.CharField(max_length=50, choices=SOURCES, default='web')

    mesa_categoria = models.ForeignKey(MesaCategoria, related_name='cargas', on_delete=models.CASCADE)
    fiscal = models.ForeignKey('fiscales.Fiscal', on_delete=models.CASCADE)
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
        tuplas = (f'{o}-{v}' for (o, v) in self.opcion_votos().order_by('opcion__orden'))
        self.firma = '|'.join(tuplas)
        self.save(update_fields=['firma'])

    def opcion_votos(self):
        """
        Devuelve una lista de los votos para cada opción.
        """
        return self.reportados.values_list('opcion', 'votos')

    def listado_de_opciones(self):
        """
        Devuelve una lista de los ids de las opciones de esta carga.
        """
        return self.reportados.values_list('opcion__id', flat=True)

    def save(self, *args, **kwargs):
        """
        si el fiscal es troll, la carga nace invalidada y ya procesada
        """
        if self.id is None and self.fiscal is not None and self.fiscal.troll:
            self.invalidada = True
            self.procesada = True
        super().save(*args, **kwargs)

    def __str__(self):
        str_invalidada = ' (invalidada) ' if self.invalidada else ' '
        return f'carga {self.tipo}{str_invalidada}de {self.mesa} / {self.categoria} por {self.fiscal}'

    def __sub__(self, carga_2):
        # arranco obteniendo los votos ordenados por opcion, que me van a ser utiles varias veces
        reportados_1 = self.reportados.order_by('opcion__orden')
        reportados_2 = carga_2.reportados.order_by('opcion__orden')

        # antes que nada: si las cargas son incomparables, o los conjuntos de opciones no coinciden,
        # la comparación se considera incorrecta
        if self.mesa_categoria != carga_2.mesa_categoria or self.tipo != carga_2.tipo:
            raise CargasIncompatiblesError("las cargas no coinciden en mesa, categoría o tipo")

        opciones_1 = [ov.opcion.id for ov in reportados_1]
        opciones_2 = [ov.opcion.id for ov in reportados_2]
        if opciones_1 != opciones_2:
            raise CargasIncompatiblesError("las cargas no coinciden en sus opciones")

        diferencia = sum(abs(r1.votos - r2.votos) for r1, r2 in zip(reportados_1, reportados_2))
        return diferencia


class VotoMesaReportado(models.Model):
    """
    Representa una "celda" del acta a cargar, es decir, dada una carga
    que define mesa y categoria, existe una instancia de este modelo
    para cada opción y su correspondiente cantidad de votos.
    """
    carga = models.ForeignKey(Carga, related_name='reportados', on_delete=models.CASCADE)
    opcion = models.ForeignKey(Opcion, on_delete=models.CASCADE)
    votos = models.PositiveIntegerField()

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
    circuitos = models.ManyToManyField(Circuito, through='AgrupacionCircuito', related_name='agrupaciones')

    class Meta:
        verbose_name = 'Agrupación de Circuitos'
        verbose_name_plural = 'Agrupaciones de Cicuitos'

    def __str__(self):
        return f'Agrupación de circuitos {self.nombre}'


class AgrupacionCircuito(models.Model):
    circuito = models.ForeignKey('Circuito', on_delete=models.CASCADE)
    agrupacion = models.ForeignKey('AgrupacionCircuitos', on_delete=models.CASCADE)


class ConfiguracionComputo(models.Model):
    """
    Definición de modos de computar resultados por distrito.
    """
    nombre = models.CharField(max_length=100)
    fiscal = models.ForeignKey(
        'fiscales.Fiscal',
        on_delete=models.CASCADE,
        related_name='configuracion_computo',
    )

    class Meta:
        ordering = ('nombre', )
        verbose_name = 'Configuración para cómputo'
        verbose_name_plural = 'Configuraciones para cómputo'
        constraints = [
            models.UniqueConstraint(
                fields=['nombre'],
                name='nombre_unico'
            )
        ]

    def __str__(self):
        return f'Configuración de cómputo {self.nombre}'


class ConfiguracionComputoDistrito(models.Model):
    """
    Definición de modos de computar resultados para un distrito, de acuerdo a un usuario.
    """
    configuracion = models.ForeignKey(ConfiguracionComputo, on_delete=models.CASCADE, related_name='configuraciones')
    distrito = models.ForeignKey(Distrito, on_delete=models.CASCADE)
    agregacion = models.CharField(max_length=30, choices=TIPOS_DE_AGREGACIONES)
    opciones = models.CharField(max_length=30, choices=OPCIONES_A_CONSIDERAR)
    proyeccion = models.ForeignKey(TecnicaProyeccion, on_delete=models.SET_NULL, default=None, null=True, blank=True)

    class Meta:
        verbose_name = 'Configuración para cómputo por distrito'
        verbose_name_plural = 'Configuraciones para cómputo por distrito'
        constraints = [
            models.UniqueConstraint(fields=['configuracion', 'distrito'],
                                    name='distrito_unico'
                                    )
        ]

    @property
    def fiscal(self):
        return self.configuracion.fiscal


class CargaOficialControl(models.Model):
    """
    Este modelo se agrega para guardar la fecha y hora del último registro de
    carga parcial oficial obtenido desde la planilla de cálculo de gdocs
    """
    fecha_ultimo_registro = models.DateTimeField()
    categoria = models.ForeignKey('Categoria', on_delete=models.CASCADE, default=None)


@receiver(post_save, sender=Mesa)
def actualizar_electores(sender, instance=None, created=False, **kwargs):
    """
    Actualiza las denormalizaciones de cantidad de electores a nivel circuito, seccion y distrito
    cada vez que se crea o actualiza una instancia de mesa.

    En general, esto sólo debería ocurrir en la configuración inicial del sistema.
    """
    if instance.lugar_votacion:
        lugar = instance.lugar_votacion
        circuito = lugar.circuito

        seccion = circuito.seccion
        distrito = seccion.distrito

        electores = Mesa.objects.filter(
            lugar_votacion=lugar
        ).aggregate(v=Sum('electores'))['v'] or 0
        lugar.electores = electores
        lugar.save(update_fields=['electores'])

        # circuito
        electores = Mesa.objects.filter(lugar_votacion__circuito=circuito, ).aggregate(v=Sum('electores')
                                                                                       )['v'] or 0
        circuito.electores = electores
        circuito.save(update_fields=['electores'])

        # seccion
        electores = Mesa.objects.filter(lugar_votacion__circuito__seccion=seccion
                                        ).aggregate(v=Sum('electores'))['v'] or 0
        seccion.electores = electores
        seccion.save(update_fields=['electores'])

        # distrito
        electores = Mesa.objects.filter(lugar_votacion__circuito__seccion__distrito=distrito
                                        ).aggregate(v=Sum('electores'))['v'] or 0
        distrito.electores = electores
        distrito.save(update_fields=['electores'])


@receiver(post_save, sender=Categoria)
def actualizar_prioridades_categoria(sender, instance, created, **kwargs):
    from scheduling.models import registrar_prioridad_categoria

    if created or instance.tracker.has_changed('prioridad'):
        registrar_prioridad_categoria(instance)
        MesaCategoria.recalcular_orden_de_carga_para_categoria(instance)


@receiver(post_save, sender=Seccion)
def actualizar_prioridades_seccion(sender, instance, created, **kwargs):
    from scheduling.models import registrar_prioridades_seccion

    if created or instance.tracker.has_changed('prioridad_hasta_2') \
        or instance.tracker.has_changed('cantidad_minima_prioridad_hasta_2') \
            or instance.tracker.has_changed('prioridad_2_a_10')  \
    or instance.tracker.has_changed('prioridad_10_a_100'):
        registrar_prioridades_seccion(instance)
        MesaCategoria.recalcular_orden_de_carga_para_seccion(instance)


@receiver(pre_save, sender=Distrito)
@receiver(pre_save, sender=Seccion)
@receiver(pre_save, sender=Circuito)
@receiver(pre_save, sender=LugarVotacion)
@receiver(pre_save, sender=Mesa)
@receiver(pre_save, sender=SeccionPolitica)
@receiver(pre_save, sender=Partido)
def canonizar_numero(sender, instance, *args, **kwargs):
    instance.numero = canonizar(instance.numero)
