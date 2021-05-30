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
    distrito_nro,escuela_nro,escuela,direccion,circuito_nro,seccion_nro,localidad,desde,hasta,cant_mesas,latitud,longitud
    1,32493,ESC Nº26 HIPOLITO YRIGOYEN,SAN JUAN AV 353 ,1,1,CIUDAD DE BUENOS AIRES,1,12,12,,
    1,32501,ESC Nº3 BERNARDINO RIVADAVIA,BOLIVAR 1235 ,1,1,CIUDAD DE BUENOS AIRES,21,30,10,,
    '''
    help = "Importar escuelas"

    def handle(self, *args, **options):
        super().handle(*args, **options)

        reader = DictReader(self.file.open())

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
                self.warning(f'No existe el circuito {circuito_nro}. {mensaje_fallo_escuela}')
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

                mensaje_mesas = f'No se crean mesas para la escuela {escuela}. Línea {c}.'
                try:
                    mesa_desde = int(row['desde'])
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
                        try:
                            mesa, created = Mesa.objects.update_or_create(numero=mesa_nro,
                                                                          lugar_votacion=escuela,
                                                                          circuito=circuito,
                                                                          electores=ELECTORES_MESA_DEFAULT
                            )
                        except IntegrityError:
                            self.warning(f'Error de integridad al intentar crear la mesa {mesa_nro} '
                                         f'en la escuela {escuela}. Línea {c}'
                            )
                            continue
                        self.log_creacion(mesa, created, level=4)

                else:
                    self.warning(f'El total de mesas {mesas_total} no coincide con el '
                                 f'rango {mesa_desde}-{mesa_hasta}.'
                                 f'Se crean las mesas {mesa_desde} hasta {mesa_hasta}. Línea {c}.'
                    )
