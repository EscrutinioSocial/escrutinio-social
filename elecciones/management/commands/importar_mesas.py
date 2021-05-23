from decimal import Decimal
from django.conf import settings
from pathlib import Path
from django.db.utils import IntegrityError
from csv import DictReader
from elecciones.models import Distrito, Seccion, Circuito, LugarVotacion, Mesa, Categoria, canonizar
import datetime

from .basic_command import BaseCommand


class Command(BaseCommand):
    ''' Formato de archivo: mesas-electores.csv
    distrito,seccion,circuito,lugar_votacion,mesa,electores
    '''
    help = "Crea las mesas y actualiza electores"

#    formato = ['distrito', 'seccion', 'circuito','lugar_votacion', 'mesa', 'electores']

    # def copiar_mesa(self, circuito, mesa_nueva):
    #     otra_mesa = Mesa.objects.filter(circuito=circuito).exclude(id=mesa_nueva.id).first()
    #     if not otra_mesa:
    #         self.warning(f"No hay mesas en circuito {circuito}.")
    #         return

    #     # Le copiamos las categorías.
    #     for categoria in otra_mesa.categorias.all():
    #         mesa_nueva.categoria_add(categoria)

    #     # Y el lugar de votación.
    #     mesa_nueva.lugar_votacion = otra_mesa.lugar_votacion
    #     mesa_nueva.save(update_fields=['lugar_votacion'])

    def handle(self, *args, **options):
        super().handle(*args, **options)

        reader = DictReader(self.CSV.open())
#        reader = DictReader(self.CSV.open(), self.formato)
        fallos = []
        for c, row in enumerate(reader, 1):
            self.log(
                f"{row['distrito']}, {row['seccion']}, {row['circuito']}, {row['lugar_votacion']}, {row['mesa']}, {row['electores']}",
                level=3
            )

            nro_distrito = canonizar(row['distrito'])
            nro_seccion = canonizar(row['seccion'])
            nro_circuito = canonizar(row['circuito'])
            nro_lugar_votacion = canonizar(row['lugar_votacion'])
            nro_mesa = canonizar(row['mesa'])
            nro_electores = row['electores']

            mensaje_fallo_mesa = f'No se pudo procesar la línea {c}. ({nro_distrito},{nro_seccion},{nro_circuito},{nro_lugar_votacion},{nro_mesa})'

            try:
                distrito = Distrito.objects.get(numero=nro_distrito)
                seccion = Seccion.objects.get(numero=nro_seccion, distrito=distrito)
                circuito = Circuito.objects.get(numero=nro_circuito, seccion=seccion)
                escuela = LugarVotacion.objects.get(numero=nro_lugar_votacion)
            except Distrito.DoesNotExist:
                fallo = f'No existe el distrito {nro_distrito}. {mensaje_fallo_mesa}'
                fallos.append(fallo)
                self.warning(fallo)
            except Seccion.DoesNotExist:
                fallo = f'No existe la sección {nro_seccion} en el distrito {distrito}. {mensaje_fallo_mesa}'
                fallos.append(fallo)
                self.warning(fallo)
            except Circuito.DoesNotExist:
                fallo = f'No existe el circuito {nro_circuito} en el distrito {distrito}. {mensaje_fallo_mesa}'
                fallos.append(fallo)
                self.warning(fallo)
            except LugarVotacion.DoesNotExist:
                fallo = f'No existe lugar de votacion {nro_lugar_votacion} en el circuito {circuito}-{seccion}-{distrito}. La creamos.'
                fallos.append(fallo)
                self.warning(fallo)

            else:
                try:
                    mesa, created = Mesa.objects.update_or_create(numero=nro_mesa,
                                                                 lugar_votacion=escuela,
                                                                 circuito=circuito,
                                                                 electores=nro_electores
                                )
                except IntegrityError:
                    self.warning(f'Error de integridad al intentar crear la mesa {nro_mesa} '
                                 f'en la escuela {escuela}. Línea {c}'
                    )
                    continue
                self.log_creacion(mesa, created, level=4)


        self.log(f'Se procesaron {c} líneas.', level=1)
        for fallo in fallos:
            self.error_log(fallo)
