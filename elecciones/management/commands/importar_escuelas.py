from decimal import Decimal
from django.conf import settings
from pathlib import Path
from django.db.utils import IntegrityError
from csv import DictReader
from elecciones.models import Distrito, Seccion, Circuito, LugarVotacion, Mesa, Categoria
import datetime

from .basic_command import BaseCommand

ELECTORES_MESA_DEFAULT = 350

ESTADO_GEOLOCALIZACION = {
    'Match': 9,
    'Partial Match': 5,
}


class Command(BaseCommand):
    ''' Formato de archivo: escuelas.csv
    distrito_nro,escuela_nro,escuela,direccion,circuito_nro,seccion_nro,localidad,latitud,longitud
    1,32493,ESC Nº26 HIPOLITO YRIGOYEN,SAN JUAN AV 353 ,1,1,CIUDAD DE BUENOS AIRES,,
    1,32501,ESC Nº3 BERNARDINO RIVADAVIA,BOLIVAR 1235 ,1,1,CIUDAD DE BUENOS AIRES,,
    '''
    help = "Importar escuelas"

    def handle(self, *args, **options):
        super().handle(*args, **options)

        reader = DictReader(self.CSV.open())

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
                seccion = Seccion.objects.get(numero=nro_seccion, distrito=distrito)
                circuito = Circuito.objects.get(numero=row['circuito_nro'].strip(), seccion=seccion)
            except Distrito.DoesNotExist:
                self.warning(f'No existe el distrito {nro_distrito}. {mensaje_fallo_escuela}')
            except Seccion.DoesNotExist:
                self.warning(f'No existe la sección {nro_seccion} en el distrito {nro_distrito}. Línea {c}. '
                             f'{mensaje_fallo_escuela}'
                )
            except Circuito.DoesNotExist:
                self.warning(f'No existe el circuito {nro_circuito}. {mensaje_fallo_escuela}')
            else:

                escuela, created = LugarVotacion.objects.update_or_create(
                    circuito=circuito,
                    nombre=row['escuela'],
                    direccion=row['direccion'],
                    numero=nro_escuela,
                    ciudad=row['localidad'] or '',
                    )

                # Idealmente deberíamos tener el número de electores por escuela, al menos.
                # escuela.electores = int(row['electores']) #no los tenemos por ahora

                coordenadas = (self.to_float(row['longitud']), self.to_float(row['latitud']))
                if isinstance(coordenadas[0], float) and isinstance(coordenadas[1], float):
                    info_geolocalizacion = {'type': 'Point', 'coordinates': coordenadas}
                    estado_geolocalizacion = ESTADO_GEOLOCALIZACION['Match']
                else:
                    info_geolocalizacion = None
                    estado_geolocalizacion = 0
                escuela.actualizar_geom(info_geolocalizacion, estado_geolocalizacion)

                self.log_creacion(escuela, created)

