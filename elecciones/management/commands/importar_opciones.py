from decimal import Decimal
from django.conf import settings
from django.db.models import Q
from django.db.utils import IntegrityError
from pathlib import Path
from csv import DictReader
from elecciones.models import Partido, Opcion, Categoria, CategoriaOpcion
from django.db import transaction

from .basic_command import BaseCommand


class Command(BaseCommand):
    """
    Formato:
        partido_nombre,partido_nombre_corto,partido_codigo,partido_color,opcion_nombre,opcion_nombre_corto,partido_orden,orden,categoria_slug
        FRENTE DE TODOS,FRENTE DE TODOS,136,,CELESTE Y BLANCA A,CELESTE Y BLANCA A,1,1,Presidente_y_Vicepresidente
    """
    help = "Importar partidos y opciones y los asocia a las categorías correspondientes."


    def handle(self, *args, **options):
        super().handle(*args, **options)

        reader = DictReader(self.CSV.open())

        for linea, row in enumerate(reader, 1):

            # Categoría
            categoria_slug = row['categoria_slug']
            categoria = Categoria.objecs.get(slug=categoria_slug)

            # Partido.
            codigo = row['partido_codigo']
            nombre = row['partido_nombre']
            nombre_corto = row['partido_nombre_corto'][:30]
            color = row['partido_color']

            defaults = {
                'nombre': nombre,
                'nombre_corto': nombre_corto,
                'color': color,
            }
            partido, created = Partido.objects.update_or_create(codigo=codigo, defaults=defaults)

            self.log_creacion(partido, created)

            # Opción.
            nombre = row['opcion_nombre']

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

            orden = self.to_nat(row, 'orden', linea)
            if orden is None:
                self.error_log(f'No se estableció el orden para la opción {nombre} en '
                                'la categoría {categoria}. Línea {linea}.')

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
