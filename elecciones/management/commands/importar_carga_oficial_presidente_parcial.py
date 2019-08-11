from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
import requests
from datetime import datetime
import pytz
from fiscales.models import Fiscal
from elecciones.models import (
    Distrito,
    Mesa,
    Carga,
    Seccion,
    Circuito,
    Categoria,
    MesaCategoria,
    VotoMesaReportado,
    CargaOficialControl,
    Opcion
)

# If modifying these scopes, delete the file token.pickle.
URL = 'https://sheets.googleapis.com/v4/spreadsheets/1hnn-BCqilu2jXZ-lcNiwhDa_V-QTCSp-EMqhpz4y2fA/values/A:XX'
API_KEY = '***REMOVED***'
# The ID and range of a sample spreadsheet.
PARAMS = {'key': API_KEY}


class Command(BaseCommand):

    def handle(self, *args, **options):
        r = requests.get(url=URL, params=PARAMS)
        values = r.json()['values']
        ultima_guardada_con_exito = None
        tz = pytz.timezone('America/Argentina/Buenos_Aires')

        if values:
            # acá se debería consultar la fecha y hora del último registro guardado
            # para luego filtrar las filas nuevas
            fecha_ultimo_registro = CargaOficialControl.objects.first()
            if fecha_ultimo_registro:
                date_format = '%d/%m/%Y %H:%M:%S'
                # fd = datetime.strptime(fecha_ultimo_registro.fecha_ultimo_registro, date_format)
                head, *tail = values
                tail = map(lambda x: dict(zip(head, x)), tail)
                # filtro para quedarme con los datos nuevos
                datos_a_guardar = filter(lambda x: datetime.strptime(x['Marca temporal'], '%d/%m/%Y %H:%M:%S').replace(tzinfo=tz) > fecha_ultimo_registro.fecha_ultimo_registro, tail)
            else:
                head, *tail = values
                datos_a_guardar = map(lambda x: dict(zip(head, x)), tail)

            categoria_presidente = Categoria.objects.get(nombre=settings.NOMBRE_CATEGORIA_PRESI_Y_VICE)
            fiscal = Fiscal.objects.get(id=1)
            tipo = 'parcial_oficial'

            opcion_nosotros = Opcion.objects.get(partido__codigo=settings.CODIGO_PARTIDO_NOSOTROS)
            opcion_ellos = Opcion.objects.get(partido__codigo=settings.CODIGO_PARTIDO_ELLOS)
            opcion_blancos = Opcion.blancos()
            opcion_nulos = Opcion.nulos()
            opcion_total = Opcion.total_votos()

            for row in datos_a_guardar:

                nro_distrito = row['Distrito']
                nro_seccion = row['Seccion']
                try:
                    distrito = Distrito.objects.get(numero=nro_distrito)
                    seccion = Seccion.objects.get(numero=nro_seccion, distrito=distrito)
                    circuito = Circuito.objects.get(numero=row['Circuito'].strip(), seccion=seccion)
                    mesa = Mesa.objects.get(numero=row['Mesa'], circuito=circuito)
                    mesa_categoria = MesaCategoria.objects.get(mesa=mesa, categoria=categoria_presidente)

                    # TODO
                    # INICIO TRANSACCION
                    # ESTA PARTE DEBERIA ESTAR EN UNA TRANSACCION Y HACER
                    # UN ROLLBACK EN CASO DE QUE FALLE
                    carga = Carga.objects.create(
                        mesa_categoria=mesa_categoria,
                        tipo=tipo,
                        fiscal=fiscal,
                        origen=Carga.SOURCES.csv
                    )

                    VotoMesaReportado.objects.create(carga=carga, opcion=opcion_nosotros, votos=row['136-Frente de Todos'])
                    VotoMesaReportado.objects.create(carga=carga, opcion=opcion_ellos, votos=row['135-JxC'])
                    VotoMesaReportado.objects.create(carga=carga, opcion=opcion_blancos, votos=row['Blancos'])
                    VotoMesaReportado.objects.create(carga=carga, opcion=opcion_nulos, votos=row['Nulos'])
                    VotoMesaReportado.objects.create(carga=carga, opcion=opcion_total, votos=row['Total'])

                    # Si hay cargas repetidas esto hace que se tome la ultima
                    # en el proceso de comparar_mesas_con_correo
                    mesa_categoria.actualizar_parcial_oficial(carga)

                    # FIN TRANSACCION

                    ultima_guardada_con_exito = datetime.strptime(row['Marca temporal'], '%d/%m/%Y %H:%M:%S').replace(tzinfo=tz)

                except Distrito.DoesNotExist:
                    self.warning('No existe el distrito %s.' % nro_distrito)
                except Seccion.DoesNotExist:
                    self.warning('No existe la sección %s en el distrito %s.' % (nro_seccion, nro_distrito))
                except Circuito.DoesNotExist:
                    self.warning('No existe el circuito %s' % row)

            if ultima_guardada_con_exito:
                if fecha_ultimo_registro:
                    fecha_ultimo_registro.fecha_ultimo_registro = ultima_guardada_con_exito
                    fecha_ultimo_registro.save()
                else:
                    CargaOficialControl.objects.create(fecha_ultimo_registro=ultima_guardada_con_exito)
