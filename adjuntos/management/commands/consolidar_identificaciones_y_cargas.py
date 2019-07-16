from django.core.management.base import BaseCommand
from adjuntos.consolidacion import consumir_novedades
import logging

logger = logging.getLogger("e-va")


class Command(BaseCommand):
    help = "Consolidador asincrónico"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        consumir_novedades()
