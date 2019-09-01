from django.core.management.base import BaseCommand
from django.conf import settings
from adjuntos.consolidacion import consumir_novedades
import time
import structlog


logger = structlog.get_logger('consolidador')


class Command(BaseCommand):
    help = "Consolidador asincrónico"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        while True:
            n_identificaciones, n_cargas, n_mesacategorias_y_attachments = consumir_novedades()
            logger.debug(
                'consolidacion',
                identificaciones=n_identificaciones,
                cargas=n_cargas
            )
            time.sleep(settings.PAUSA_CONSOLIDACION)
