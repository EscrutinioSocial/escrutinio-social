from django.core.management.base import BaseCommand
from elecciones.models import Opcion, Partido, Categoria
import datetime


class Command(BaseCommand):
    help = "Crear las opciones en las categorias disponibles"

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
        op.tipo = Opcion.TIPOS.metadata
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
        op.tipo = Opcion.TIPOS.metadata
        op.save()

        self.stdout.write(self.style.WARNING('Conectando las opciones a las categorias'))
        fecha = datetime.datetime(2019, 5, 12, 8, 0)
        categorias = Categoria.objects.filter(fecha=fecha)
        self.stdout.write(self.style.WARNING('Se encontraron {} categorias'.format(categorias.count())))

        opciones = Opcion.objects.all()
        for categoria in categorias:
            self.stdout.write(self.style.SUCCESS('Categoria {}'.format(categoria.nombre)))

            for opcion in opciones:
                self.stdout.write(self.style.SUCCESS('  -- Opcion {}'.format(opcion.nombre)))

                # --------------------------------------------------------------------------------
                # FIXME proximas elecciones:
                # en la carga de partidos ya debería definirse a que categoria se presenta cada uno
                if opcion.partido:
                    if categoria.slug != 'intendente-cordoba-2019' and opcion.partido.nombre_corto == 'Libres del Sur':
                        # Olgita no tiene candidato a cobernador
                        self.stdout.write(self.style.WARNING(' -- -- Ignorado'))
                        continue
                # --------------------------------------------------------------------------------

                if opcion not in categoria.opciones.all():
                    categoria.opciones.add(opcion)
                    categoria.save()
                    self.stdout.write(self.style.SUCCESS(' -- -- Conectado'))
                else:
                    self.stdout.write(self.style.WARNING(' -- -- YA ESTABA'))

        self.stdout.write(self.style.SUCCESS('Terminado'))

