from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Distrito, Seccion, Circuito, LugarVotacion, Mesa, Categoria
import datetime

CSV = Path(settings.BASE_DIR) / 'elecciones/data/escuelas.csv'

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
    ''' formato de archivo: escuelas.csv
    distrito_nro,escuela_nro,escuela,direccion,circuito_nro,seccion_nro,localidad,desde,hasta,cant_mesas,latitud,longitud
    1,32493,ESC Nº26 HIPOLITO YRIGOYEN,SAN JUAN AV 353 ,1,1,CIUDAD DE BUENOS AIRES,1,12,12,,
    1,32501,ESC Nº3 BERNARDINO RIVADAVIA,BOLIVAR 1235 ,1,1,CIUDAD DE BUENOS AIRES,21,30,10,,
    '''
    help = "Importar escuelas total pais"

    def handle(self, *args, **options):
        fecha = datetime.datetime(2019, 5, 12, 8, 0)

        reader = DictReader(CSV.open())

        for c, row in enumerate(reader, 1):
            print (c,row['distrito_nro'],row['seccion_nro'],row['circuito_nro'],row['escuela_nro'])
            try:
                distrito = Distrito.objects.get(numero=row['distrito_nro'])
                seccion  = Seccion.objects.get (numero=row['seccion_nro'], distrito=distrito)
                circuito = Circuito.objects.get(numero=row['circuito_nro'].strip(), seccion=seccion)
            except # era Distrito.DoesNotExist:
                print ('No existe el distrito, seccion o circuito ', row)

            escuela, created = LugarVotacion.objects.update_or_create( #era get_or_create
                circuito=circuito,
                nombre=row['escuela'],
                direccion=row['direccion'],
                numero=row['escuela_nro'],
                ciudad=row['localidad'] or '',
#                barrio=row['Barrio'] or ''
                )

#            escuela.electores = int(row['electores']) #no los tenemos aca
            
            coordenadas = [to_float(row['longitud']), to_float(row['latitud'])]
            if coordenadas[0] and coordenadas[1]:
                geom = {'type': 'Point', 'coordinates': coordenadas}
                if row['estado_geolocalizacion'] == 'Match':
                    estado_geolocalizacion = 9
                elif row['estado_geolocalizacion'] == 'Partial Match':
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
                mesa, created = Mesa.objects.get_or_create(numero=mesa_nro,lugar_votacion=escuela,circuito=circuito)  # EVITAR duplicados en limpiezas de escuelas y otros
#                mesa.lugar_votacion=escuela
#                mesa.circuito=circuito
                #mesa.electores=escuela.electores/(int(row['hasta']) + 1- int(row['desde'])) # habria que guardar escuela.mesas en el modelo
                mesa.save()

                self.log(mesa, created)


