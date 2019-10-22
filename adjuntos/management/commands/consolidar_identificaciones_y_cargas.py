from django.core.management.base import BaseCommand
from django.conf import settings

import time
import structlog

from adjuntos.consolidacion import consumir_novedades
from scheduling.scheduler import scheduler


logger = structlog.get_logger('consolidador')


def consolidador(cant_por_iteracion=500, ejecutado_desde=''):
    msg = f'Consolidación desde {ejecutado_desde}' if ejecutado_desde != '' else 'Consolidación'
    n_identificaciones, n_cargas = consumir_novedades(cant_por_iteracion)
    logger.debug(
        msg,
        identificaciones=n_identificaciones,
        cargas=n_cargas
    )


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
            consolidador(cant_por_iteracion)
            time.sleep(settings.PAUSA_CONSOLIDACION)
