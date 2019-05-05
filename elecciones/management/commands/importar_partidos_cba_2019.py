from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Partido
import datetime

CSV = Path(settings.BASE_DIR) / 'elecciones/data/partidos-cba-2019.csv'

class Command(BaseCommand):
    help = "Importar lista de partidos"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Leyendo CSV'))

        reader = DictReader(CSV.open())

        errores = []
        c = 0
        for row in reader:
            c += 1
            # Partido,codigo,nombre corto,gobernador,intendente capital
            partido = row['Partido']
            codigo_partido = row['codigo']
            corto = row['nombre corto']
            #TODO activar modelos con candidatos si queremos mostrarlo
            candidato_gobiernador = row['gobernador']
            candidato_intendente = row['intendente capital']
            orden = int(row['orden'])

            nombre = f'{partido} {codigo_partido}'
            partido, created = Partido.objects.get_or_create(orden=orden,
                                                                numero=100,
                                                                codigo=codigo_partido,
                                                                nombre=nombre,
                                                                nombre_corto=corto)
            
            self.stdout.write(self.style.SUCCESS(f'Cargado {nombre}'))