from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from adjuntos.models import *
from adjuntos.consolidacion import *

class Command(BaseCommand):
    help = "Consolidador asincrónico"

    def add_arguments(self, parser):
        pass


    def handle(self, *args, **options):
        consumir_novedades_identificacion()