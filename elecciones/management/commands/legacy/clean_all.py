from django.conf import settings
from django.core.management.base import BaseCommand
from elecciones.models import (Categoria, Mesa, Seccion, Circuito,
                                LugarVotacion, MesaCategoria, Partido, Opcion)
from adjuntos.models import Attachment, Email


class Command(BaseCommand):
    help = "Borrar toda la base"

    mensaje = ('¡Caca Nene! Estás por borrar toda la base. Estás seguro? Si efectivamente '
              ' querés borrarla, abrí el archivo y descomentá la línea que hace eso.'
            )
    def handle(self, *args, **options):
        borrar = [Categoria, Mesa, Seccion, Circuito, LugarVotacion,
                    MesaCategoria, Partido, Opcion, Attachment, Email
                    ]
        self.stdout.write(self.style.WARN(''))

        for model in borrar:
            self.stdout.write(self.style.SUCCESS(f'eliminando {model}'))
            # model.objects.all().delete()

