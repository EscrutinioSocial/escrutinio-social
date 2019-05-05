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


class escrutinio_socialBaseCommand(BaseCommand):

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


class Command(escrutinio_socialBaseCommand):
    help = "Importar carta marina"

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

