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
    distrito,seccion,circuito,mesa,nro
    '''
    help = "Define la cantidad de electores por mesa."

    formato = ['distrito', 'seccion', 'circuito', 'mesa', 'numero']

    def copiar_mesa(self, circuito, mesa_nueva):
        otra_mesa = Mesa.objects.filter(circuito=circuito).exclude(id=mesa_nueva.id).first()
        if not otra_mesa:
            self.warning(f"No hay mesas en circuito {circuito}.")
            return

        # Le copiamos las categorías.
        for categoria in otra_mesa.categorias.all():
            mesa_nueva.categoria_add(categoria)

        # Y el lugar de votación.
        mesa_nueva.lugar_de_votacion = otra_mesa.lugar_de_votacion
        mesa_nueva.save(update_fields=['lugar_de_votacion'])

    def handle(self, *args, **options):
        super().handle(*args, **options)

        reader = DictReader(self.CSV.open(), self.formato)
        fallos = []
        for c, row in enumerate(reader, 1):
            self.log(
                f"{row['distrito']}, {row['seccion']}, {row['circuito']}, {row['mesa']}, {row['numero']}",
                level=3
            )

            nro_distrito = canonizar(row['distrito'])
            nro_seccion = canonizar(row['seccion'])
            nro_circuito = canonizar(row['circuito'])
            nro_mesa = canonizar(row['mesa'])
            cant = row['numero']

            mensaje_fallo_mesa = f'No se pudo procesar la línea {c}. ({nro_distrito},{nro_seccion},{nro_circuito},{nro_mesa})'

            try:
                distrito = Distrito.objects.get(numero=nro_distrito)
                seccion = Seccion.objects.get(numero=nro_seccion, distrito=distrito)
                circuito = Circuito.objects.get(numero=nro_circuito, seccion=seccion)
                mesa = Mesa.objects.get(circuito=circuito, numero=nro_mesa)
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
            except Mesa.DoesNotExist:
                fallo = f'No existe la mesa {nro_mesa} en el circuito {circuito}-{seccion}-{distrito}. La creamos.'
                
                mesa = Mesa.objects.create(
                    numero=nro_mesa,
                    circuito=circuito,
                    electores=cant
                )
                fallos.append(fallo)
                self.warning(fallo)
                self.copiar_mesa(circuito, mesa)
            else:
                mesa.electores = cant
                mesa.save(update_fields=['electores'])

                self.log(f'Se actualizó la cantidad de electores de la mesa {mesa.id}', level=3)

        self.log(f'Se procesaron {c} líneas.', level=1)
        for fallo in fallos:
            self.error_log(fallo)
