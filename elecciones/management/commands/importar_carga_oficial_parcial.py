from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
import requests
from django.db import transaction
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
    Opcion,
    CategoriaOpcion
)

# If modifying these scopes, delete the file token.pickle.
API_KEY = '***REMOVED***'
# The ID and range of a sample spreadsheet.
PARAMS = {'key': API_KEY}


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            "--categoria", type=str, dest="categoria",
            help="Slug de categoría a analizar (default %(default)s).",
            default=settings.SLUG_CATEGORIA_PRESI_Y_VICE
        )

    def get_opcion(self, codigo_partido):
        return CategoriaOpcion.objects.get(opcion__partido__codigo=codigo_partido, categoria=self.categoria).opcion

    def get_opcion_nosotros(self):
        return self.get_opcion(settings.CODIGO_PARTIDO_NOSOTROS)

    def get_opcion_ellos(self):
        return self.get_opcion(settings.CODIGO_PARTIDO_ELLOS)

    def handle(self, *args, **options):
        slug_categoria = options['categoria']
        self.categoria = Categoria.objects.get(slug=slug_categoria)
        print("Vamos a importar la categoría:", self.categoria)

        url = settings.URL_ARCHIVO_IMPORTAR_CORREO[slug_categoria]
        r = requests.get(url=url, params=PARAMS)
        values = r.json()['values']
        ultima_guardada_con_exito = None
        tz = pytz.timezone('America/Argentina/Buenos_Aires')

        if values:
            # acá se debería consultar la fecha y hora del último registro guardado
            # para luego filtrar las filas nuevas
            fecha_ultimo_registro = CargaOficialControl.objects.filter(categoria=self.categoria).first()
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

            fiscal = Fiscal.objects.get(id=1)
            tipo = 'parcial_oficial'

            opcion_nosotros = self.get_opcion_nosotros()
            opcion_ellos = self.get_opcion_ellos()
            opcion_blancos = Opcion.blancos()
            opcion_nulos = Opcion.nulos()
            opcion_total = Opcion.total_votos()
            opciones = [opcion_nosotros, opcion_ellos, opcion_blancos, opcion_nulos, opcion_total]
            for row in datos_a_guardar:

                nro_distrito = row['Distrito']
                nro_seccion = row['Seccion']
                try:
                    distrito = Distrito.objects.get(numero=nro_distrito)
                    seccion = Seccion.objects.get(numero=nro_seccion, distrito=distrito)
                    circuito = Circuito.objects.get(numero=row['Circuito'].strip(), seccion=seccion)
                    mesa = Mesa.objects.get(numero=row['Mesa'], circuito=circuito)
                    mesa_categoria = MesaCategoria.objects.get(mesa=mesa, categoria=self.categoria)

                    with transaction.atomic:
                        carga = Carga.objects.create(
                            mesa_categoria=mesa_categoria,
                            tipo=tipo,
                            fiscal=fiscal,
                            origen=Carga.SOURCES.csv
                        )

                        votos_a_crear = []
                        for nombre_opcion, opcion in zip(['136-Frente de Todos', '135-JxC', 'Blancos', 'Nulos', 'Total'], opciones):
                            votos_a_crear.append(
                                VotoMesaReportado(
                                    carga=carga, opcion=opcion,
                                    votos=row[nombre_opcion]
                                )
                            )
                        VotoMesaReportado.objects.bulk_create(votos_a_crear)
                        # actualizo la firma así no es necesario correr consolidar_identificaciones_y_cargas
                        carga.actualizar_firma()

                        # Si hay cargas repetidas esto hace que se tome la última
                        # en el proceso de comparar_mesas_con_correo.
                        mesa_categoria.actualizar_parcial_oficial(carga)

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
                    CargaOficialControl.objects.create(fecha_ultimo_registro=ultima_guardada_con_exito, categoria=self.categoria)
