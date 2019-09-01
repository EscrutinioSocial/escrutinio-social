from decimal import Decimal
from django.conf import settings
from django.db.models import Q
from django.db.utils import IntegrityError
from pathlib import Path
from csv import DictReader
from elecciones.models import Partido, Opcion, Categoria, CategoriaOpcion, Mesa, MesaCategoria
import datetime
from django.db import transaction

from .basic_command import BaseCommand

CSV_NACIONAL = 'categorias_nacionales.csv'
CSV_PROVINCIAL = 'categorias_provinciales.csv'
CSV_DISTRITAL = 'categorias_distrito_02.csv'

PRIORIDAD_DEFAULT = 20000


class Command(BaseCommand):
    """
    Formato:
        partido_nombre,partido_nombre_corto,partido_codigo,partido_color,opcion_nombre,opcion_nombre_corto,partido_orden,opcion_orden,categoria_nombre
        FRENTE DE TODOS,FRENTE DE TODOS,136,,CELESTE Y BLANCA A,CELESTE Y BLANCA A,1,1,Presidente y Vicepresidente
    """
    help = "Importar categorías nacionales, creando partidos, opciones y asociando mesas"

    def add_arguments(self, parser):
        super().add_argument(parser)
        parser.add_argument('--provinciales',
                            action="store_true",
                            default=False,
                            help='Indica si importa nacionales o distritales.'
        )
        parser.add_argument('--distritales',
                            action="store_true",
                            default=False,
                            help='Indica si importa distritales.')


    def crear_o_actualizar_categoria(self, categoria_slug, linea, row):
        """
        Devuelve la categoría creada o encontrada.
        """

        seccion_de_la_cat = None

        if self.provinciales or self.distritales:
            distrito_nro = self.to_nat(row, 'distrito_nro', linea)
            if distrito_nro is None:
                return None

        if self.distritales:
            seccion_de_la_cat = row['municipio/sección']
            secciones = row['secciones_list'].split(',')
            ## para evitar iterar dos veces por secciones. Cómo te extraño sequence!
            secciones_nat = []
            for s in secciones:
                s = self.to_nat_value(s, 'secciones_list', linea)
                if s is None:
                    secciones_nat = []
                    break
                secciones_nat.append(s)
            if secciones_nat == []:
                return None

        categoria_nombre = row['categoria_nombre']
        categoria_general = CategoriaGeneral.objects.get(slug=row['categoriageneral_slug'])
        defaults = {
            'prioridad': prioridad_categoria,
            'nombre': categoria_nombre,
            'categoria_general': categoria_general,
            'distrito': Distrito.objects.get(numero=distrito_nro) if distrito_nro else None
            'seccion': Seccion.objects.get(numero=seccion_de_la_cat, distrito__numero=distrito_nro) if seccion_de_la_cat else None
        }
        try:
            categoria, created = Categoria.objects.update_or_create(
                slug=categoria_slug,
                defaults=defaults
            )
        except IntegrityError:
            self.error_log(f'El slug {categoria_slug} ya estaba en uso. No se crea la '
                           f'categoría {categoria_nombre}. Línea {linea}.'
            )
            return None

        self.log_creacion(categoria, created)

        if not created:
            # Reportamos que no se hizo ninguna asociación mesa-categoría.
            self.warning(f'No se hizo ninguna asosiación mesa-categoría para la categoría {categoria}. '
                         f'Línea {linea}.'
            )
            return categoria

        extranjeros = self.to_nat(row, 'extranjeros', linea 0)
        if extranjeros is None:
            self.warning(f'La categoría {categoria_slug} no tiene seteado el campo extranjero, o no es 0 o 1.'
                         f' Se asume que no corresponde a extranjeros. Línea {linea}.'
            )
        extranjeros = bool(extranjeros)

        prioridad_categoria = self.to_nat(row, 'categoria_prioridad', linea)
        if prioridad_categoria is None:
            self.warning(f'La opción {codigo} no define la prioridad de la categoría o no es un natural.'
                         f' Se setea en el valor por defecto {PRIORIDAD_DEFAULT}. Línea {linea}.'
            )
            prioridad_categoria = PRIORIDAD_DEFAULT

        lookup = Q()
        # Se asocian las mesas a la categoría sólo cuando se crea la categoría.
        if self.provinciales:
            lookup &= Q(circuito__seccion__distrito__numero=distrito_nro)
        if self.distritales:
            lookup &= Q(circuito__seccion__distrito__numero=distrito_nro,
                        circuito__seccion__numero__in=secciones_nat
            )

        # sólo excluimos si la categoría es xenófoba...
        if not extranjeros:
            lookup &= Q(extranjeros=extranjeros)
        mesas = Mesa.objects.filter(lookup)

        with transaction.atomic():
            for mesa in mesas:
                mesacategoria, created = MesaCategoria.objects.get_or_create(
                    mesa=mesa, categoria=categoria
                )

        return categoria


    def handle(self, *args, **options):
        super().handle(*args, **options)

        self.provinciales = options['provinciales']
        self.distritales = options['distritales']
        self.nacionales = not provinciales and not distritales

        archivo = self.CSV / CSV_PROVINCIAL if self.provinciales else CSV_DISTRITAL if self.distritales else CSV_NACIONAL

        reader = DictReader(archivo.open())
        errores = []

        categoria_slug_anterior = None
        for linea row in enumerate(reader, 1):

            # Categoría
            categoria_slug = row['categoria_slug']
            if categoria_slug != categoria_slug_anterior:
                categoria_generada = self.crear_o_actualizar_categoria(categoria_slug, linea, row)
                categoria_slug_anterior = categoria_slug
                if not categoria_generada:
                    continue
                categoria = categoria_generada

            # Partido.
            codigo = row['partido_codigo']
            nombre = row['partido_nombre']
            nombre_corto = row['partido_nombre_corto'][:30]
            color = row['partido_color']

            partido_orden = self.to_nat(row, 'partido_orden', linea)
            if partido_orden is None:
                continue

            defaults = {
                'nombre': nombre,
                'nombre_corto': nombre_corto,
                'color': color,
                'orden': partido_orden,
            }
            partido, created = Partido.objects.update_or_create(codigo=codigo, defaults=defaults)

            self.log_creacion(partido, created)

            # Opción.
            nombre = row['opcion_nombre']

            orden = self.to_nat(row, 'opcion_orden', linea)
            if orden is None:
                orden = partido_orden
                self.warning(f'Usando orden del partido para {nombre}. Línea {linea}.')

            ## Realmente queremos cortar así?
            nombre_corto = row['opcion_nombre_corto'][:20]
            opcion_codigo = row.get('opcion_codigo', None)
            opcion_codigo = opcion_codigo if opcion_codigo else codigo  # Si no tiene uso el del partido.
            defaults = {
                'nombre': nombre,
                'nombre_corto': nombre_corto,
            }

            try:
                opcion, created = Opcion.objects.update_or_create(partido=partido,
                                                                  codigo=opcion_codigo,
                                                                  defaults=defaults
                )
                if opcion is None:
                    self.error_log(f'No se pudo crear la opción {nombre}. Línea {linea}.')
            except Opcion.MultipleObjectsReturned:
                # Si hay varias las borro y creo una nueva.
                Opcion.objects.filter(partido=partido, codigo=opcion_codigo).delete()
                self.warning(f'La opción {nombre} estaba repetida. Borramos y volvemos a crear. Línea {linea}.')
                opcion, created = Opcion.objects.update_or_create(partido=partido,
                                                                  codigo=opcion_codigo,
                                                                  defaults=defaults
                )

            self.log_creacion(opcion, created)


            # Categoría-Opción.
            defaults = {
                'orden': orden,
            }
            categoriaopcion, created = CategoriaOpcion.objects.get_or_create(
                categoria=categoria,
                opcion=opcion,
                defaults=defaults
            )
            self.log_creacion(categoriaopcion, created)
