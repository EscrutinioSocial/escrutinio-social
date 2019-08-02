from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Seccion, Circuito, Distrito
import datetime

CSV = Path(settings.BASE_DIR) / 'elecciones/data/circuitos_paso_nacional_2019.csv'


def to_float(val):
    try:
        return float(val.replace(',', '.'))
    except:
        return None


class BaseCommand(BaseCommand):

    def success(self, msg, ending='\n'):
        self.stdout.write(self.style.SUCCESS(msg), ending=ending)

    def warning(self, msg, ending='\n'):
        self.stdout.write(self.style.WARNING(msg), ending=ending)

    def log(self, object, created=True, ending='\n'):
        if created:
            self.success(f'Creado {object}', ending=ending)


class Command(BaseCommand):
    help = "Importar hasta circuitos"

    def handle(self, *args, **options):
        reader = DictReader(CSV.open())

        for c, row in enumerate(reader, 1):
            distrito_nro = row['distrito_nro']
            distrito_name = row['distrito_name']
            seccion_nro = row['seccion_nro']
            seccion_name = row['seccion_name']
            circuito_nro = row['circuito_nro']
            circuito_name = row['circuito_name']

            distrito, created = Distrito.objects.get_or_create(nombre=distrito_name, numero=distrito_nro)
            self.log(distrito, created)
            
            seccion, created = Seccion.objects.get_or_create(
                distrito=distrito, nombre=seccion_name, numero=seccion_nro)
            self.log(seccion, created)

            circuito, created = Circuito.objects.get_or_create(
                seccion=seccion, nombre=circuito_name, numero=circuito_nro)
            self.log(circuito, created)

