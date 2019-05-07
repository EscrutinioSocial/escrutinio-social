from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Seccion, Circuito, LugarVotacion, Mesa, Eleccion
import datetime

CSV = Path(settings.BASE_DIR) / 'elecciones/data/mesas-cordoba-2019-gobernador.csv'
"""
Seccion,SeccionNombre,Circuito,CircuitoNombre,Mesa,Establecimiento,Domicilio,TipoMesa,CantElectores,Secc-Circuito
1,Capital,1,SECCIONAL PRIMERA,1,CENTRO EDUC.NIVEL MEDIO ADULTO,DEAN FUNES 417,Mixto,340,1-1 Capital - SECCIONAL PRIMERA
1,Capital,1,SECCIONAL PRIMERA,2,CENTRO EDUC.NIVEL MEDIO ADULTO,DEAN FUNES 417,Mixto,343,1-1 Capital - SECCIONAL PRIMERA
"""

def to_float(val):
    try:
        return float(val.replace(',', '.'))
    except:
        return None


class BaseCommand(BaseCommand):

    def success(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def warning(self, msg):
        self.stdout.write(self.style.WARNING(msg))

    def error(self, msg):
        self.stdout.write(self.style.ERROR(msg))

    def log(self, object, created=True):
        if created:
            self.success(f'creado {object}')
        else:
            self.warning(f'{object} ya existe')


class Command(BaseCommand):
    help = "Importar carta marina"

    """ hay 3 mesas que son de una escuela y no son nros consecutivos
    Se requiere copiar la mesa 1 3 veces antes de tirar este comando para que no falten esos tres datos

from elecciones.models import Mesa
mesa_8651 = Mesa.objects.get(numero=1)
mesa_8651.pk = None
mesa_8651.numero = 8651
mesa_8651.save()

mesa_8652 = Mesa.objects.get(numero=1)
mesa_8652.pk = None
mesa_8652.numero = 8652
mesa_8652.save()

mesa_8653 = Mesa.objects.get(numero=1)
mesa_8653.pk = None
mesa_8653.numero = 8653
mesa_8653.save()
    """

    def handle(self, *args, **options):
        reader = DictReader(CSV.open())

        errores = []
        c = 0
        for row in reader:
            c += 1
            mesa_nro = int(row['Mesa'])
            electores = int(row['CantElectores'])

            if electores < 1:
                err = f'La mesa {mesa_nro} tiene {electores} electores'
                self.error(err)
                errores.append(err)
                continue

            if electores > 405:
                err = f'La mesa {mesa_nro} tiene {electores} electores'
                self.error(err)
                errores.append(err)
                continue

            # YA DEBEN ESTAR CARGADAS LAS MESAS CON EL OTRO IMPORTADOR
            try:
                mesa = Mesa.objects.get(numero=mesa_nro)
            except Mesa.DoesNotExist:
                err = f'La mesa {mesa_nro} NO EXISTE'
                self.error(err)
                errores.append(err)
                continue

            mesa.electores = electores
            mesa.save()

            self.stdout.write(self.style.SUCCESS(f"Mesa {mesa_nro}: {electores} electores"), ending='\r')

        self.success(f"Se procesaron {c} mesas con {len(errores)} errores")
        for error in errores:
            self.error(error)

