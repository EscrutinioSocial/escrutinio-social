from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Seccion, Circuito, Distrito
import datetime

CSV = Path(settings.BASE_DIR) / 'elecciones/data/2019/paso-nacional/circuitos.csv'


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

            try:
                distrito = Distrito.objects.get(numero=distrito_nro)

                if distrito.nombre != distrito_name:
                    distrito.nombre = distrito_name
                    distrito.save(update_fields=['nombre'])
            except Distrito.DoesNotExist:
                distrito = Distrito.objects.create(nombre=distrito_name, numero=distrito_nro)
                self.log(distrito, True)

            try:
                seccion = Seccion.objects.get(numero=seccion_nro)

                if seccion.nombre != seccion_name:
                    seccion.nombre = seccion_name
                    seccion.save(update_fields=['nombre'])

                if seccion.distrito != distrito:
                    seccion.distrito = distrito
                    seccion.save(update_fields=['distrito'])
            except Seccion.DoesNotExist:
                seccion = Seccion.objects.create(
                    distrito=distrito, nombre=seccion_name, numero=seccion_nro)
                self.log(seccion, True)

            try:
                circuito = Circuito.objects.get(numero=circuito_nro)

                if circuito.nombre != circuito_name:
                    circuito.nombre = circuito_name
                    circuito.save(update_fields=['nombre'])

                if circuito.seccion != seccion:
                    circuito.seccion = seccion
                    circuito.save(update_fields=['seccion'])
            except Circuito.DoesNotExist:
                circuito = Circuito.objects.create(
                    seccion=seccion, nombre=circuito_name, numero=circuito_nro)
                self.log(circuito, True)
