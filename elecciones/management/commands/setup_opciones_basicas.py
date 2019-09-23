from django.core.management.base import BaseCommand
from django.conf import settings
from elecciones.models import Opcion, CategoriaOpcion, Categoria


class Command(BaseCommand):
    help = "Crea las opciones básicas definidas en settings."

    defaults = {
        'BLANCOS': ('Votos en blanco', 10000),
        'NULOS': ('Votos nulos', 10001),
        'TOTAL_VOTOS': ('Total de votos', 10002),
        'TOTAL_SOBRES': ('Total de sobres', 10003),
    }

    def handle(self, *args, **options):
        for constant, (nombre_default, orden) in Command.defaults.items():
            criterio_dict = getattr(settings, f'OPCION_{constant}')

            # Si viene nombre en el criterio lo usamos como default
            nombre = criterio_dict['nombre'] if 'nombre' in criterio_dict else nombre_default

            opcion, creada = Opcion.objects.get_or_create(
                **criterio_dict,
                defaults={'nombre': nombre, 'orden': orden},
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
                _, creada = CategoriaOpcion.objects.get_or_create(
                    categoria=categoria, opcion=opcion
                )
                if creada:
                    self.stdout.write(
                        self.style.SUCCESS(f'     se asoció a {categoria}.')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'     ya estaba asociada a {categoria}')
                    )
