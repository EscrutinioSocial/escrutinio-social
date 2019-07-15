from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from adjuntos.models import *
from adjuntos.consolidacion import *
import logging

logger = logging.getLogger("e-va")
UMBRAL_ITERACIONES_NOTIF = 10000

class Command(BaseCommand):
    help = "Consolidador asincrónico"

    def add_arguments(self, parser):
        pass


    def handle(self, *args, **options):
        iteracion = 0
        while True:
            consumir_novedades()
            if iteracion == UMBRAL_ITERACIONES_NOTIF:
                logger.debug("Consumiendo novedades.")
                iteracion = 0
            iteracion = iteracion + 1
