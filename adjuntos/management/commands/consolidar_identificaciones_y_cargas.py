from django.core.management.base import BaseCommand
from django.conf import settings
from adjuntos.consolidacion import consumir_novedades
import time
import structlog


logger = structlog.get_logger('consolidador')


class Command(BaseCommand):
    help = "Consolidador asincrónico"

    def add_arguments(self, parser):
        parser.add_argument("--cant",
            type=int, default=100,
            help="Cantidad de elementos a procesar por corrida (None es sin límite, default %(default)s)."
        )

    def handle(self, *args, **options):
        cant_por_iteracion = options['cant']
        while True:
            n_identificaciones, n_cargas = consumir_novedades(cant_por_iteracion)
            logger.debug(
                'Consolidación',
                identificaciones=n_identificaciones,
                cargas=n_cargas
            )
            time.sleep(settings.PAUSA_CONSOLIDACION)
