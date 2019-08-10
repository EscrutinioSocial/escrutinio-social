from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Seccion, Circuito, Distrito
import datetime

from .basic_command import BaseCommand

CSV = Path(settings.BASE_DIR) / 'elecciones/data/2019/paso-nacional/circuitos.csv'


def to_float(val):
    try:
        return float(val.replace(',', '.'))
    except:
        return None




class Command(BaseCommand):
    help = "Importar hasta circuitos"

    def handle(self, *args, **options):
        self.verbosity = int(options['verbosity'])
        reader = DictReader(CSV.open())

        for c, row in enumerate(reader, 1):
            distrito_nro = self.canonizar(row['distrito_nro'])
            distrito_name = row['distrito_name']
            seccion_nro = self.canonizar(row['seccion_nro'])
            seccion_name = row['seccion_name']
            circuito_nro = self.canonizar(row['circuito_nro'])
            circuito_name = row['circuito_name']

            try:
                distrito = Distrito.objects.get(numero=distrito_nro)

                if distrito.nombre != distrito_name:
                    distrito.nombre = distrito_name
                    distrito.save(update_fields=['nombre'])
            except Distrito.DoesNotExist:
                distrito = Distrito.objects.create(nombre=distrito_name, numero=distrito_nro)
                self.log_creacion(distrito, True)

            try:
                seccion = Seccion.objects.get(numero=seccion_nro, distrito=distrito)

                if seccion.nombre != seccion_name:
                    seccion.nombre = seccion_name
                    seccion.save(update_fields=['nombre'])

                if seccion.distrito != distrito:
                    seccion.distrito = distrito
                    seccion.save(update_fields=['distrito'])
            except Seccion.DoesNotExist:
                seccion = Seccion.objects.create(
                    distrito=distrito, nombre=seccion_name, numero=seccion_nro)
                self.log_creacion(seccion, True)

            try:
                circuito = Circuito.objects.get(numero=circuito_nro, seccion=seccion)

                if circuito.nombre != circuito_name:
                    circuito.nombre = circuito_name
                    circuito.save(update_fields=['nombre'])

                if circuito.seccion != seccion:
                    circuito.seccion = seccion
                    circuito.save(update_fields=['seccion'])
            except Circuito.DoesNotExist:
                circuito = Circuito.objects.create(
                    seccion=seccion, nombre=circuito_name, numero=circuito_nro)
                self.log_creacion(circuito, True)
