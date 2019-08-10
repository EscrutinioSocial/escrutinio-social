from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Seccion, Circuito, LugarVotacion, Mesa, Categoria
import datetime


class Command(BaseCommand):
    help = "Darle colores a las elecciones."

    def handle(self, *args, **options):

        categoria = Categoria.objects.get(slug='gobernador-cordoba-2019')
        categoria.color = '#330022'
        categoria.back_color = '#AAFFDD'
        categoria.save()

        categoria = Categoria.objects.get(slug='intendente-cordoba-2019')
        categoria.color = '#DD1122'
        categoria.back_color = '#77AAFF'
        categoria.save()

        categoria = Categoria.objects.get(slug='legisladores-dist-unico-cordoba-2019')
        categoria.color = '#115522'
        categoria.back_color = '#AAAAEE'
        categoria.save()

        #categoria = Categoria.objects.get(slug='tribunal-cuentas-prov-cordoba-2019')
        #categoria.color = '#FF3322'
        #categoria.back_color = '#0022AA'
        #categoria.save()



