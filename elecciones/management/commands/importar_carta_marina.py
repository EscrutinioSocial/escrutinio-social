from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Seccion, Circuito, LugarVotacion, Mesa


CSV = Path(settings.BASE_DIR) / 'elecciones/data/escuelas-elecciones-2017-cordoba-Geolocalizada.csv'

def to_float(val):
    try:
        return float(val.replace(',', '.'))
    except:
        return None



class escrutinio_socialBaseCommand(BaseCommand):

    def success(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def warning(self, msg):
        self.stdout.write(self.style.WARNING(msg))

    def log(self, object, created=True):
        if created:
            self.success(f'creado {object}')
        else:
            self.warning(f'{object} ya existe')


class Command(escrutinio_socialBaseCommand):
    help = "Importar carta marina"

    def handle(self, *args, **options):
        reader = DictReader(CSV.open())

        for row in reader:
            seccion, created = Seccion.objects.get_or_create(nombre=row['seccion_name'], numero=row['seccion_nro'])
            self.log(seccion, created)
            circuito, created = Circuito.objects.get_or_create(
                nombre=row['circuito_name'], numero=row['circuito_nro'], seccion=seccion
            )
            self.log(circuito, created)

            coordenadas = [to_float(row['Longitud']), to_float(row['Latitud'])]
            if coordenadas[0] and coordenadas[1]:
                geom = {'type': 'Point', 'coordinates': coordenadas}
            else:
                geom = None

            escuela, created = LugarVotacion.objects.get_or_create(
                circuito=circuito,
                nombre=row['escuela'],
                direccion=row['direccion'],
                ciudad=row['ciudad'] or '',
                barrio=row['barrio'] or '',
                geom=geom,
                electores=int(row['electores'])
            )
            self.log(escuela, created)
            if created:
                for mesa_nro in range(int(row['desde']), int(row['hasta']) + 1):
                    mesa, created = Mesa.objects.get_or_create(numero=mesa_nro, lugar_votacion=escuela, circuito=circuito)
                    self.log(mesa, created)

