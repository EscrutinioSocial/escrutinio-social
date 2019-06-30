from django.conf import settings
from django.core.management.base import BaseCommand
from elecciones.models import (Categoria, Mesa, Seccion, Circuito,
                                LugarVotacion, MesaCategoria, Partido, Opcion)
from adjuntos.models import Attachment, Email


class Command(BaseCommand):
    help = "Borrar toda la base"

    def handle(self, *args, **options):
        borrar = [Categoria, Mesa, Seccion, Circuito, LugarVotacion,
                    MesaCategoria, Partido, Opcion, Attachment, Email
                    ]
        for model in borrar:
            self.stdout.write(self.style.SUCCESS(f'eliminando {model}'))
            model.objects.all().delete()

