from django.core.management.base import BaseCommand
from django.conf import settings
from adjuntos.consolidacion import consumir_novedades
import logging
import time


logger = logging.getLogger("e-va")


class Command(BaseCommand):
    help = "Consolidador asincrónico"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        while True:
            n_identificaciones, n_cargas = consumir_novedades()
            logger.debug("Identificaciones: %d, cargas: %d.", n_identificaciones, n_cargas)
            time.sleep(settings.PAUSA_CONSOLIDACION)
