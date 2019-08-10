from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Seccion, Circuito, Distrito
import datetime

CSV = Path(settings.BASE_DIR) / 'elecciones/data/2019/paso-nacional/prioridad_scheduling.csv'


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

    def log(self, message, level=3, ending='\n', ):
        self.verbosity = self.verbosity if self.verbosity else 1
        if level <= self.verbosity:
            self.success(f'{message}', ending=ending)


class Command(BaseCommand):
    help = "Importar hasta circuitos"
    
    def to_nat(self, value, field_name, n):
        """conversión de un string a un natural"""
        try:
            value = int(value)
        except ValueError:
            self.log(f'El valor {value} del campo {field_name} en la fila {n} no es un entero',0)
            return None

        if value <= 0:
            self.log(f'El valor {value} del campo {field_name} en la fila {n} no es positivo',0)
            return None
        return value
        
    def handle(self, *args, **options):

        self.verbosity = options.get('verbosity',1)
        reader = DictReader(CSV.open())

        for c, row in enumerate(reader, 1):
            seccion_nombre = row['seccion_nombre']
            distrito_nro = row['distrito_nro']
            seccion_nro = row['seccion_nro']
            hasta_2 = row['hasta_2']
            hasta_10 = row['hasta_10']
            desde_10 = row['desde_10']

            try:
                seccion = Seccion.objects.get(numero=seccion_nro, distrito__numero=distrito_nro)
            except Seccion.DoesNotExist:
                distrito = Distrito.objects.get(numero=distrito_nro)
                self.log(f'La sección {seccion_nombre} no existe en el distrito {distrito}',0)
                continue

            # chequeamos tener naturales
            hasta_2 = self.to_nat(hasta_2,'hasta_2',c)
            if hasta_2 is None:
                continue
            hasta_10 = self.to_nat(hasta_10,'hasta_10',c)
            if hasta_10 is None:
                continue
            desde_10 = self.to_nat(desde_10,'desde_10',c)
            if desde_10 is None:
                continue

            seccion.prioridad_hasta_2 = hasta_2
            seccion.prioridad_2_a_10 = hasta_10
            seccion.prioridad_10_a_100 = desde_10
            seccion.save()
            self.log(f'Seteamos prioridades ({hasta_2},{hasta_10},{desde_10}) para la sección '
                     f'{seccion.nombre} en el distrito {seccion.distrito}.',
                     2
            )
