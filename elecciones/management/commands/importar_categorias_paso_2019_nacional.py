from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db.models import Q
from pathlib import Path
from csv import DictReader
from elecciones.models import Partido, Opcion, Categoria, CategoriaOpcion, Mesa, MesaCategoria
import datetime
from django.db import transaction

from .basic_command import BaseCommand

CSV_NACIONAL = Path(settings.BASE_DIR) / 'elecciones/data/2019/paso-nacional/categorias_nacionales.csv'
CSV_PROVINCIAL = Path(settings.BASE_DIR) / 'elecciones/data/2019/paso-nacional/categorias_provinciales.csv'


class Command(BaseCommand):
    """partido_nombre,partido_nombre_corto,partido_codigo,partido_color,opcion_nombre,opcion_nombre_corto,partido_orden,opcion_orden,categoria_nombre
        FRENTE DE TODOS,FRENTE DE TODOS,136,,CELESTE Y BLANCA A,CELESTE Y BLANCA A,1,1,Presidente y Vicepresidente
    """
    help = "Importar categorías nacionales, creando partidos, opciones y asociando mesas"

    def add_arguments(self, parser):
        parser.add_argument('--provinciales',
                            action="store_true",
                            default=False,
                            help='Indica si importa nacionales o distritales.'
        )

    def handle(self, *args, **options):
        self.verbosity = int(options['verbosity'])
        provinciales = options['provinciales']

        archivo = CSV_PROVINCIAL if provinciales else CSV_NACIONAL

        reader = DictReader(archivo.open())
        errores = []

        for c, row in enumerate(reader, 1):
            codigo = row['partido_codigo']
            nombre = row['partido_nombre']
            nombre_corto = row['partido_nombre_corto'][:30]
            color = row['partido_color']

            orden = self.to_nat(row, 'partido_orden', c)
            if orden is None:
                continue

            defaults = {
                'nombre': nombre,
                'nombre_corto': nombre_corto,
                'color': color,
                'orden': orden,
            }            
            partido, created = Partido.objects.update_or_create(codigo=codigo, defaults=defaults)

            self.log_creacion(partido, created)
            
            if provinciales:
                distrito_nro = self.to_nat(row, 'distrito_nro', c)
                if distrito_nro is None:
                    continue

            orden = self.to_nat(row, 'opcion_orden', c)
            if orden is None:
                continue

            nombre = row['opcion_nombre']            
            ## Realmente queremos cortar así?
            nombre_corto = row['opcion_nombre_corto'][:20]
            
            opcion_codigo = row.get('opcion_codigo', None)
            opcion_codigo = opcion_codigo if opcion_codigo else codigo # Si no tiene uso el del partido.
            defaults = {
                'nombre': nombre,
                'nombre_corto': nombre_corto,
                'orden': orden,
            }        

            
            opcion, created = Opcion.objects.update_or_create(partido=partido,
                                                              codigo=opcion_codigo,
                                                              defaults=defaults
            )
            if opcion is None:
                self.error_log(f'No se pudo crear la opción {nombre}. Línea {c}')

            self.log_creacion(opcion, created)

            categoria, created = Categoria.objects.get_or_create(
                nombre=row['categoria_nombre'],
                slug=row['categoria_slug']
            )
            self.log_creacion(categoria, created)

            if created:
                # Se asocian las mesas a la categoría sólo cuando se crea la categoría.
                lookup = Q()
                if provinciales:
                    lookup = Q(circuito__seccion__distrito__numero=distrito_nro) 
                mesas = Mesa.objects.filter(lookup).all()

                with transaction.atomic():
                    for mesa in mesas:
                        mesacategoria, created = MesaCategoria.objects.get_or_create(
                            mesa=mesa, categoria=categoria
                        )
            # Reportamos que no se hizo ninguna asociación mesa-categoría.
            else:
                self.warning(f'No se hizo ninguna asoción mesa-categoría para la categoría {categoria}. '
                             f'Línea {c}.'
                )

            categoriaopcion, created = CategoriaOpcion.objects.get_or_create(
                categoria=categoria,
                opcion=opcion,
            )
            self.log_creacion(categoriaopcion, created)
