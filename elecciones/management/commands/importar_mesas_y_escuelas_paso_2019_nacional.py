from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Distrito, Seccion, Circuito, LugarVotacion, Mesa, Categoria
import datetime

CSV = Path(settings.BASE_DIR) / 'elecciones/data/2019/paso-nacional/escuelas.csv'

ESTADO_GEOLOCALIZACION = {
    'Match': 9,
    'Partial Match': 5,
}

def to_float(val):
    try:
        return float(val.replace(',', '.'))
    except:
        return None


class BaseCommand(BaseCommand):

    def log(self, message, level=2, ending='\n'):
        if level <= self.verbosity:
            self.stdout.write(message, ending=ending)
            
    def success(self, msg, level=3, ending='\n'):
        self.log(self.style.SUCCESS(msg), level, ending=ending)

    def warning(self, msg, level=1, ending='\n'):
        self.log(self.style.WARNING(msg), level, ending=ending)

    def error_log(self, msg, ending='\n'):
        self.log(self.style.FAIL(msg), 0, ending=ending)
        
    def log_creacion(self, object, created=True, level=3, ending='\n'):
        modelo = object._meta.model.__name__
        if created:
            self.success(f'Se creó el/la {modelo} {object}', level, ending)
        else:
            self.warning(f'El/La {modelo} {object} ya existe', level, ending)


class Command(BaseCommand):
    ''' formato de archivo: escuelas.csv
    distrito_nro,escuela_nro,escuela,direccion,circuito_nro,seccion_nro,localidad,desde,hasta,cant_mesas,latitud,longitud
    1,32493,ESC Nº26 HIPOLITO YRIGOYEN,SAN JUAN AV 353 ,1,1,CIUDAD DE BUENOS AIRES,1,12,12,,
    1,32501,ESC Nº3 BERNARDINO RIVADAVIA,BOLIVAR 1235 ,1,1,CIUDAD DE BUENOS AIRES,21,30,10,,
    '''
    help = "Importar escuelas"

    def handle(self, *args, **options):
        self.verbosity = int(options['verbosity'])
        fecha = datetime.datetime(2019, 5, 12, 8, 0)

        reader = DictReader(CSV.open())

        for c, row in enumerate(reader, 1):
            self.log(f"{row['distrito_nro']}, {row['seccion_nro']}, {row['circuito_nro']}, {row['escuela_nro']}",
                     level=3
            )

            nro_distrito = row['distrito_nro']
            nro_seccion = row['seccion_nro']
            nro_circuito = row['circuito_nro']
            nro_escuela = row['escuela_nro']
            mensaje_fallo_escuela = f'No se procesa la escuela {nro_escuela}. Línea {c}.'

            try:
                distrito = Distrito.objects.get(numero=nro_distrito)
                seccion  = Seccion.objects.get(numero=nro_seccion, distrito=distrito)
                circuito = Circuito.objects.get(numero=row['circuito_nro'].strip(), seccion=seccion)
            except Distrito.DoesNotExist:
                self.warning(f'No existe el distrito {nro_distrito}. {mensaje_fallo_escuela}')
            except Seccion.DoesNotExist:
                self.warning('No existe la sección {nro_seccion} en el distrito {nro_distrito}. Línea {c}. '
                             f'{mensaje_fallo_escuela}'
                )
            except Circuito.DoesNotExist:
                self.warning('No existe el circuito {circuito_nro}. {mensaje_fallo_escuela}')
            else:

                escuela, created = LugarVotacion.objects.update_or_create(
                    circuito=circuito,
                    nombre=row['escuela'],
                    direccion=row['direccion'],
                    numero=nro_escuela,
                    ciudad=row['localidad'] or '',
                    )

                ## Idealmente deberíamos tener el número de electores por escuela, al menos.
                # escuela.electores = int(row['electores']) #no los tenemos aca
                
                coordenadas = (to_float(row['longitud']), to_float(row['latitud']))
                if isinstance(coordenadas[0],float) and isinstance(coordenadas[1],float):
                    info_geolocalizacion = {'type': 'Point', 'coordinates': coordenadas}
                    estado_geolocalizacion = ESTADO_GEOLOCALIZACION['Match']
                else:
                    info_geolocalizacion = None
                    estado_geolocalizacion = 0
                escuela.geom = info_geolocalizacion
                escuela.estado_geolocalizacion = estado_geolocalizacion
                escuela.save()

                self.log_creacion(escuela, created)
                
                mensaje_mesas = f'No se crean mesas para la escuela {escuela}. Línea {c}.'
                try:
                    mesa_desde=int(row['desde'])
                except ValueError:
                    self.warning('No está definido el campo _desde_. {mensaje_mesas}')
                    continue
                
                try:
                    mesa_hasta = int(row['hasta'])
                except ValueError:
                    self.warning(f'No está definido el campo _hasta_. {mensaje_mesas}')
                    continue

                mesa_hasta = mesa_hasta + 1

                try:
                    mesas_total = int(row['cant_mesas'])
                except ValueError:
                    mesas_total = None
                    self.warning('No está definido el campo _hasta_.'
                                 f'Se crean mesas desde {mesa_desde} hasta {mesa_hasta}. Línea {c}.'
                    )
                    
                if mesas_total == mesa_hasta - mesa_desde:
                    for mesa_nro in range(mesa_desde, mesa_hasta):
                        mesa, created = Mesa.objects.update_or_create(numero=mesa_nro,lugar_votacion=escuela,circuito=circuito) 
                        mesa.save()
                        self.log_creacion(mesa, created, level=4)
                else:
                    self.warning(f'El total de mesas {mesas_total} no coincide con el rango {mesa_desde}-{mesa_hasta}.'
                                 f'Se crean las mesas {mesa_desde} hasta {mesa_hasta}. Línea {c}.'
                    )
                    


