from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Seccion, Circuito, LugarVotacion, Mesa, Eleccion
import datetime

CSV = Path(settings.BASE_DIR) / 'elecciones/data/escuelas-elecciones-2019-cordoba-gobernador.csv'

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

        fecha = datetime.datetime(2019, 5, 12, 8, 0) 
        eleccion, created = Eleccion.objects.get_or_create(slug='gobernador-cordoba-2019', nombre='Gobernador Córdoba 2019', fecha=fecha)

        for row in reader:
            seccion, created = Seccion.objects.get_or_create(nombre=row['Nombre Seccion'], numero=row['Seccion'])
            self.log(seccion, created)
            circuito, created = Circuito.objects.get_or_create(
                nombre=row['Nombre Circuito'], numero=row['Circuito'], seccion=seccion
            )
            self.log(circuito, created)

            coordenadas = [to_float(row['Longitud']), to_float(row['Latitud'])]
            if coordenadas[0] and coordenadas[1]:
                geom = {'type': 'Point', 'coordinates': coordenadas}
            else:
                geom = None

            escuela, created = LugarVotacion.objects.get_or_create(
                circuito=circuito,
                nombre=row['Establecimiento'],
                direccion=row['Direccion'],
                ciudad=row['Ciudad'] or '',
                barrio=row['Barrio'] or '',
                geom=geom,
                electores=int(row['electores'])
            )
            self.log(escuela, created)
            if created:
                for mesa_nro in range(int(row['Mesa desde']), int(row['Mesa Hasta']) + 1):
                    mesa, created = Mesa.objects.get_or_create(eleccion=eleccion, 
                                                                numero=mesa_nro,
                                                                lugar_votacion=escuela,
                                                                circuito=circuito)
                    self.log(mesa, created)

