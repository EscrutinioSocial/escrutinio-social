from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from pyexcel_io.exceptions import NoSupportingPluginFound
from pyexcel_xlsx import get_data
from csv import DictReader
from elecciones.models import LugarVotacion


def to_float(val):
    try:
        return float(val.replace(',', '.'))
    except:
        return None


class Command(BaseCommand):
    help = "Importar saneado de geolocalizacion hecho por Marcos"


    def success(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def warning(self, msg):
        self.stdout.write(self.style.WARNING(msg))


    def add_arguments(self, parser):
        parser.add_argument('xlsx')


    def handle(self, *args, **options):

        path = options['xlsx']
        try:
            data = get_data(path)
        except (AssertionError, NoSupportingPluginFound):
            raise CommandError('Archivo no válido')

        for key in data.keys():
            sheet = data[key]
            keys = sheet[0]
            for row in sheet[1:]:
                row_data = dict(zip(keys, row))
                pk = int(row_data.get('pk', 0))
                if not pk:
                    continue
                calidad = row_data['calidad']
                if calidad in ('A', 'B', 'C'):
                    lat = row_data['lat']
                    lon = row_data['lon']

                    geom = {'type': 'Point', 'coordinates': [lon, lat]}
                    escuela = LugarVotacion.objects.get(id=pk)
                    escuela.geom = geom
                    escuela.longitud = lon
                    escuela.latitud = lat
                    escuela.calidad = calidad
                    escuela.save()
                    self.success(f'actualizada {escuela} con calidad {calidad}')
                else:
                    self.warning(f'{pk} ignorada')
