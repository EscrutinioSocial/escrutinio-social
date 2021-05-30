from django.conf import settings
from csv import DictReader
from elecciones.models import Seccion, Circuito, Distrito

from .basic_command import BaseCommand


class Command(BaseCommand):
    help = "Importar hasta circuitos"

    def handle(self, *args, **options):
        super().handle(*args, **options)

        reader = DictReader(self.file.open())

        for c, row in enumerate(reader, 1):
            distrito_nro = row['distrito_nro']
            distrito_name = row['distrito_name']
            seccion_nro = row['seccion_nro']
            seccion_name = row['seccion_name']
            circuito_nro = row['circuito_nro']
            circuito_name = row['circuito_name']

            try:
                distrito = Distrito.objects.get(numero=distrito_nro)

                if distrito.nombre != distrito_name:
                    distrito.nombre = distrito_name
                    distrito.save(update_fields=['nombre'])
            except Distrito.DoesNotExist:
                distrito = Distrito.objects.create(nombre=distrito_name, numero=distrito_nro)
                self.log_creacion(distrito, True)

            try:
                seccion = Seccion.objects.get(numero=seccion_nro, distrito=distrito)

                if seccion.nombre != seccion_name:
                    seccion.nombre = seccion_name
                    seccion.save(update_fields=['nombre'])

                if seccion.distrito != distrito:
                    seccion.distrito = distrito
                    seccion.save(update_fields=['distrito'])
            except Seccion.DoesNotExist:
                seccion = Seccion.objects.create(
                    distrito=distrito, nombre=seccion_name, numero=seccion_nro)
                self.log_creacion(seccion, True)

            try:
                circuito = Circuito.objects.get(numero=circuito_nro, seccion=seccion)

                if circuito.nombre != circuito_name:
                    circuito.nombre = circuito_name
                    circuito.save(update_fields=['nombre'])

                if circuito.seccion != seccion:
                    circuito.seccion = seccion
                    circuito.save(update_fields=['seccion'])
            except Circuito.DoesNotExist:
                circuito = Circuito.objects.create(
                    seccion=seccion, nombre=circuito_name, numero=circuito_nro)
                self.log_creacion(circuito, True)
