from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Mesa
import datetime

# antes pasaron solo de capitalCSV = Path(settings.BASE_DIR) / 'elecciones/data/mesas-testigo-cba-capital-2019.csv'
CSV = Path(settings.BASE_DIR) / 'elecciones/data/mesas-testigo-cba-prov-2019.csv'


class Command(BaseCommand):
    help = "Importar lista de mesas testigo (según análisis estadísticos de uno de los partidos)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Leyendo CSV'))

        reader = DictReader(CSV.open())

        errores = []
        c = 0
        for row in reader:

            mesa_nro = int(row['mesa'])

            mesas = Mesa.objects.filter(numero=mesa_nro)
            if len(mesas) == 1:
                c += 1
                self.stdout.write(self.style.SUCCESS(f'Mesa {mesa_nro}'), ending = '\r')
                mesa = mesas[0]
                mesa.es_testigo = True  # TODO ¿es testigo solo en una categoria?
                mesa.save()
            else:
                err = 'Hay {} mesas nro {}'.format(mesas.count(), mesa_nro)
                errores.append(err)

        self.stdout.write(self.style.SUCCESS(f'{c} mesas procesadas OK'))
        if len(errores) == 0:
            self.stdout.write(self.style.SUCCESS('FIN OK'))
        else:
            self.stdout.write(self.style.WARNING('Finalizado con {} errores'.format(len(errores))))
            for error in errores:
                self.stdout.write(self.style.ERROR('  - {}'.format(error)))

