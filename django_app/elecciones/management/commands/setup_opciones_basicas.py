from django.core.management.base import BaseCommand
from django.conf import settings
from elecciones.models import Opcion, CategoriaOpcion, Categoria


class Command(BaseCommand):
    help = "Crea las opciones básicas definidas en settings."

    defaults = {
        'BLANCOS': 'Votos en blanco',
        'NULOS': 'Votos nulos',
        'TOTAL_VOTOS': 'Total de votos',
        'TOTAL_SOBRES': 'Total de sobres',
        'RECURRIDOS': 'Votos recurridos',
        'ID_IMPUGNADA': 'Votantes con identidad impugnada',
        'COMANDO_ELECTORAL': 'Votos comando electoral',
    }

    def handle(self, *args, **options):
        for constant, nombre_default in Command.defaults.items():
            criterio_dict = getattr(settings, f'OPCION_{constant}')

            # Si viene nombre en el criterio lo usamos como default
            nombre = criterio_dict['nombre'] if 'nombre' in criterio_dict else nombre_default

            opcion, creada = Opcion.objects.get_or_create(
                **criterio_dict,
                defaults={'nombre': nombre},
            )

            if creada:
                self.stdout.write(
                    self.style.SUCCESS(f'Se creó la opcion {opcion}.')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'{opcion} preexistía.')
                )
            for categoria in Categoria.objects.all():
                _, creada = CategoriaOpcion.objects.update_or_create(
                    categoria=categoria, opcion=opcion,
                    defaults={'orden': opcion.codigo}  # El orden default es el código.
                )
                if creada:
                    self.stdout.write(
                        self.style.SUCCESS(f'     se asoció a {categoria}.')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'     ya estaba asociada a {categoria}')
                    )
