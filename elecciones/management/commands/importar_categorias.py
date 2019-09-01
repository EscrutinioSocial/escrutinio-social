from decimal import Decimal
from django.conf import settings
from django.db.models import Q
from django.db.utils import IntegrityError
from pathlib import Path
from csv import DictReader
from elecciones.models import CategoriaGeneral, Categoria, CategoriaOpcion, Mesa, MesaCategoria
import datetime
from django.db import transaction

from .basic_command import BaseCommand

PRIORIDAD_DEFAULT = 20000


class Command(BaseCommand):
    """
    Formato:
        XXX Arreglar.
    """
    help = "Importar categorías asociando mesas."

    def crear_o_actualizar_categoria(self, linea, row):
        """
        Devuelve la categoría creada o encontrada.
        """

        distrito_nro = self.to_nat(row, 'distrito_nro', linea)
        seccion_nro = self.to_nat(row, 'seccion_nro', linea)
        secciones_list = row['secciones_list']

        if secciones_list:
            secciones = secciones_list.split(',')
            # Para evitar iterar dos veces por secciones. Cómo te extraño sequence!
            secciones_nat = []
            for s in secciones:
                s = self.to_nat_value(s, 'secciones_list', linea)
                if s is None:
                    secciones_nat = []
                    break
                secciones_nat.append(s)

        categoria_slug = row['slug']
        categoria_nombre = row['nombre']
        categoria_general = CategoriaGeneral.objects.get(slug=row['categoriageneral_slug'])
        defaults = {
            'prioridad': prioridad_categoria,
            'nombre': categoria_nombre,
            'categoria_general': categoria_general,
            'distrito': Distrito.objects.get(numero=distrito_nro) if distrito_nro else None
            'seccion': Seccion.objects.get(numero=seccion_nro, distrito__numero=distrito_nro) if seccion_nro else None
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
            self.warning(f'La categoría {categoria_slug} no define la prioridad de la categoría o no es un natural.'
                         f' Se setea en el valor por defecto {PRIORIDAD_DEFAULT}. Línea {linea}.'
            )
            prioridad_categoria = PRIORIDAD_DEFAULT

        lookup = Q()
        # Se asocian las mesas a la categoría sólo cuando se crea la categoría.
        if distrito_nro and not secciones_nat:
            lookup &= Q(circuito__seccion__distrito__numero=distrito_nro)
        elif distrito_nro and secciones_nat:
            lookup &= Q(circuito__seccion__distrito__numero=distrito_nro,
                        circuito__seccion__numero__in=secciones_nat
            )

        # Sólo excluimos si la categoría es xenófoba...
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

        reader = DictReader(self.CSV.open())

        for linea, row in enumerate(reader, 1):

            self.crear_o_actualizar_categoria(linea, row)

