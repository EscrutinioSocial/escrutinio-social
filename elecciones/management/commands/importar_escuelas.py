from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Distrito, Seccion, Circuito, LugarVotacion, Mesa, Categoria
import datetime

CSV = Path(settings.BASE_DIR) / 'elecciones/data/cartamarina-escuelas-elecciones-2017-cordoba.csv'

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

    def log(self, object, created=True, ending='\n'):
        if created:
            self.success(f'creado {object}', ending=ending)
        else:
            self.warning(f'{object} ya existe', ending=ending)


class Command(BaseCommand):
    ''' formato de archivo: cartamarina-escuelas-elecciones-2015-cordoba.csv
    Seccion Nro,Seccion Nombre,Circuito Nro,Circuito Nombre,Escuela,Mesas,Desde,Hasta,Electores
    1,CAPITAL,1,SECCIONAL PRIMERA,CENTRO EDUC.NIVEL MEDIO ADULTO - DEAN FUNES 417,7,1,7,2408
    
    cambiando a formato de archivo: cartamarina-escuelas-elecciones-2017-cordoba.csv
    escuela,direccion,localidad,distrito_nro,distrito_name,seccion_nro,seccion_name,circuito_nro,circuito_name,cant_mesas,desde,hasta,electores,latitud,longitud
    INST EDUC NTRA SEÑORA,INCA MANCO 3450,,4,CORDOBA,1,CAPITAL,4B,VILLA REVOL,19,246,264,6536,0,0

    
    '''
    help = "Importar carta marina"

    def handle(self, *args, **options):
        fecha = datetime.datetime(2019, 5, 12, 8, 0)

        reader = DictReader(CSV.open())

        for c, row in enumerate(reader, 1):
            num_distrito=row['distrito_nro']
            nom_distrito=row['distrito_name']
            distrito, created = Distrito.objects.get_or_create(numero=num_distrito,nombre=nom_distrito,electores=0,prioridad=3)
            distrito.save()
            self.log(distrito, created)

            print ('row:',c) # para cuando algo falla

            depto = row['seccion_name']
            numero_de_seccion = int(row['seccion_nro'])
            seccion, created = Seccion.objects.get_or_create(distrito=distrito,nombre=depto, numero=numero_de_seccion)
            self.log(seccion, created)
 
            circuito, created = Circuito.objects.get_or_create(nombre=row['circuito_name'], numero=row['circuito_nro'], seccion=seccion)
            self.log(circuito, created)

            escuela, created = LugarVotacion.objects.get_or_create(
                circuito=circuito,
                nombre=row['escuela'],
                direccion=row['direccion']
#                ciudad=row['Ciudad'] or '',
#                barrio=row['Barrio'] or ''
                )

            escuela.electores = int(row['electores'])
            
            coordenadas = [to_float(row['longitud']), to_float(row['latitud'])]
            if coordenadas[0] and coordenadas[1]:
                geom = {'type': 'Point', 'coordinates': coordenadas}
                if row['Estado Geolocalizacion'] == 'Match':
                    estado_geolocalizacion = 9
                elif row['Estado Geolocalizacion'] == 'Partial Match':
                    estado_geolocalizacion = 5
            else:
                geom = None
                estado_geolocalizacion = 0
            escuela.geom = geom
            escuela.estado_geolocalizacion = estado_geolocalizacion
            escuela.save()

            self.log(escuela, created)

            for mesa_nro in range(int(row['desde']), int(row['hasta']) + 1):
            #ojo habia caso mesas con numeros no consecutivos - prever
            #tal vez agregar las mesas en otra instancia y solo guardar los valores
                mesa, created = Mesa.objects.get_or_create(numero=mesa_nro)  # EVITAR duplicados en limpiezas de escuelas y otros
                mesa.lugar_votacion=escuela
                mesa.circuito=circuito
                mesa.electores=escuela.electores/(int(row['hasta']) + 1- int(row['desde'])) # habria que guardar escuela.mesas en el modelo
                mesa.save()

                self.log(mesa, created)


