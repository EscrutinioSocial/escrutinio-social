from decimal import Decimal
from django.conf import settings
from django.db.models import Q
from django.db.utils import IntegrityError
from pathlib import Path
from csv import DictReader
from elecciones.models import CategoriaGeneral
import datetime
from django.db import transaction

from .basic_command import BaseCommand



class Command(BaseCommand):
    """
    Formato:
        nombre,slug
    """
    help = "Importar categorías generales."

    def crear_o_actualizar_categoria_general(self, linea, row):
        """
        Devuelve la categoría creada o encontrada.
        """

        categoria_slug = row['slug']
        categoria_nombre = row['nombre']
        defaults = {
            'nombre': categoria_nombre,
        }
        try:
            categoria, created = CategoriaGeneral.objects.update_or_create(
                slug=categoria_slug,
                defaults=defaults
            )
        except IntegrityError:
            self.error_log(f'El slug {categoria_slug} ya estaba en uso. No se crea la '
                           f'categoría general {categoria_nombre}. Línea {linea}.'
            )
            return None

        self.log_creacion(categoria, created)

        return categoria

    def handle(self, *args, **options):
        super().handle(*args, **options)

        reader = DictReader(self.CSV.open())

        for linea, row in enumerate(reader, 1):

            self.crear_o_actualizar_categoria_general(linea, row)

