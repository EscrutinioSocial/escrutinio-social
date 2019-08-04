from django.core.management.base import BaseCommand
from django.conf import settings
from elecciones.models import Opcion, CategoriaOpcion, Categoria


class Command(BaseCommand):
    help = "Crea las opciones basicas definidas en el setting"

    defaults = {
        'BLANCOS': 'Votos en blanco',
        'TOTAL_VOTOS': 'Total de votos',
        'TOTAL_SOBRES': 'Total de sobres',
        'NULOS': 'Votos nulos',
    }

    def handle(self, *args, **options):
        for constant, nombre_default in Command.defaults.items():
            criterio_dict = getattr(settings, f'OPCION_{constant}')

            # estrictamente, el nombre no deberia importar para el filtro
            # si viene nombre en el criterio lo usamos como default
            # ver !111
            nombre = criterio_dict.pop('nombre', nombre_default)

            opcion, creada = Opcion.objects.get_or_create(
                **criterio_dict,
                defaults={'nombre': nombre},
            )

            if creada:
                self.stdout.write(
                    self.style.SUCCESS(f'se creó la opcion {opcion}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'{opcion} preexistía')
                )
            for categoria in Categoria.objects.all():
                _, creada = CategoriaOpcion.objects.get_or_create(
                    categoria=categoria, opcion=opcion
                )
                if creada:
                    self.stdout.write(
                        self.style.SUCCESS(f'     se asoció a {categoria}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'     ya estaba asociada a {categoria}')
                    )
