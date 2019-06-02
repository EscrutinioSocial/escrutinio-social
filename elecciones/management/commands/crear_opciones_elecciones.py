from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from pyexcel_io.exceptions import NoSupportingPluginFound
from pyexcel_xlsx import get_data
from csv import DictReader
from elecciones.models import Opcion, Partido, Eleccion
import datetime


class Command(BaseCommand):
    help = "Crear las opciones en las elecciones disponibles"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Iniciando creacion de opciones'))

        partidos = Partido.objects.all().order_by('orden')
        last_orden = 200
        for partido in partidos:
            op, created = Opcion.objects.get_or_create(partido=partido)
            op.nombre = partido.nombre
            op.nombre_corto = partido.nombre_corto
            op.orden = partido.orden
            op.obligatorio = True
            op.es_contable = True
            op.save()

            last_orden = partido.orden

        # crear opciones extras segun el acta
        last_orden += 10
        op, created = Opcion.objects.get_or_create(nombre='TOTAL VOTOS AGRUPACIONES POLITICA')
        op.nombre_corto = 'Total positivos'
        op.orden = last_orden
        op.obligatorio = True
        op.es_contable = False
        op.es_metadata = True
        op.save()

        last_orden += 10
        op, created = Opcion.objects.get_or_create(nombre='VOTOS EN BLANCO')
        op.nombre_corto = 'en blanco'
        op.orden = last_orden
        op.obligatorio = True
        op.es_contable = False
        op.save()

        last_orden += 10
        op, created = Opcion.objects.get_or_create(nombre='VOTOS NULOS')
        op.nombre_corto = 'nulos'
        op.orden = last_orden
        op.obligatorio = True
        op.es_contable = False
        op.save()

        last_orden += 10
        op, created = Opcion.objects.get_or_create(nombre='VOTOS RECURRIDOS')
        op.nombre_corto = 'recurridos'
        op.orden = last_orden
        op.obligatorio = True
        op.es_contable = False
        op.save()

        last_orden += 10
        op, created = Opcion.objects.get_or_create(nombre='TOTAL DE VOTOS ESCRUTADOS')
        op.nombre_corto = 'Total escrutados'
        op.orden = last_orden
        op.obligatorio = True
        op.es_contable = False
        op.es_metadata = True
        op.save()

        self.stdout.write(self.style.WARNING('Conectando las opciones a las elecciones'))
        fecha = datetime.datetime(2019, 5, 12, 8, 0)
        elecciones = Eleccion.objects.filter(fecha=fecha)
        self.stdout.write(self.style.WARNING('Se encontraron {} elecciones'.format(elecciones.count())))

        opciones = Opcion.objects.all()
        for eleccion in elecciones:
            self.stdout.write(self.style.SUCCESS('Eleccion {}'.format(eleccion.nombre)))

            for opcion in opciones:
                self.stdout.write(self.style.SUCCESS('  -- Opcion {}'.format(opcion.nombre)))

                # --------------------------------------------------------------------------------
                #FIXME proximas elecciones: en la carga de partidos ya debería definirse a que elecciones se presenta cada uno
                if opcion.partido:
                    if eleccion.slug != 'intendente-cordoba-2019' and opcion.partido.nombre_corto == 'Libres del Sur':
                        # Olgita no tiene candidato a cobernador
                        self.stdout.write(self.style.WARNING(' -- -- Ignorado'))
                        continue
                # --------------------------------------------------------------------------------


                if opcion not in eleccion.opciones.all():
                    eleccion.opciones.add(opcion)
                    eleccion.save()
                    self.stdout.write(self.style.SUCCESS(' -- -- Conectado'))
                else:
                    self.stdout.write(self.style.WARNING(' -- -- YA ESTABA'))



        self.stdout.write(self.style.SUCCESS('Terminado'))

