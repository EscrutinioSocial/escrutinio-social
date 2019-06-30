from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Seccion, Circuito, LugarVotacion, Mesa, Categoria
import datetime


class Command(BaseCommand):
    help = "Darle colores a las elecciones"

    def handle(self, *args, **options):

        eleccion = Categoria.objects.get(slug='gobernador-cordoba-2019')
        eleccion.color = '#330022'
        eleccion.back_color = '#AAFFDD'
        eleccion.save()

        eleccion = Categoria.objects.get(slug='intendente-cordoba-2019')
        eleccion.color = '#DD1122'
        eleccion.back_color = '#77AAFF'
        eleccion.save()

        eleccion = Categoria.objects.get(slug='legisladores-dist-unico-cordoba-2019')
        eleccion.color = '#115522'
        eleccion.back_color = '#AAAAEE'
        eleccion.save()

        #eleccion = Categoria.objects.get(slug='tribunal-cuentas-prov-cordoba-2019')
        #eleccion.color = '#FF3322'
        #eleccion.back_color = '#0022AA'
        #eleccion.save()



