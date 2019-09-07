from decimal import Decimal
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Seccion, Circuito, Distrito

from .basic_command import BaseCommand

CSV = Path(settings.BASE_DIR) / 'elecciones/data/2019/paso-nacional/prioridad_scheduling.csv'


class Command(BaseCommand):
    help = "Setea prioridades de scheduling"

    def handle(self, *args, **options):
        super().handle(*args, **options)

        reader = DictReader(self.CSV.open())

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
                self.log(f'La sección {seccion_nombre} no existe en el distrito {distrito}', 0)
                continue

            # chequeamos tener naturales
            hasta_2 = self.to_nat(row, 'hasta_2', c)
            if hasta_2 is None:
                continue
            hasta_10 = self.to_nat(row, 'hasta_10', c)
            if hasta_10 is None:
                continue
            desde_10 = self.to_nat(row, 'desde_10', c)
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
