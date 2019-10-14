from django.db.utils import IntegrityError
from django.db import transaction
from django.core.management.base import BaseCommand
from adjuntos.models import Attachment, PreIdentificacion
from problemas.models import Problema
from elecciones.models import (VotoMesaReportado, Carga, MesaCategoria)
from fiscales.models import Fiscal


class Command(BaseCommand):
    """
    Resetea el sistema salvo distritos, secciones, circuitos, lugares de votación,
    mesas, grupos, usuarios y fiscales.
    """
    help = "Resetea el sistema parcialemente."

    def handle(self, *args, **options):

        self.resetear()
        print("Reseteado.")

    @transaction.atomic
    def resetear(self):
        Attachment.objects.all().delete()
        PreIdentificacion.objects.all().delete()
        Problema.objects.all().delete()
        VotoMesaReportado.objects.all().delete()
        Carga.objects.all().delete()
        Fiscal.objects.all().update(
            last_seen=None,
            ingreso_alguna_vez=False,
            attachment_asignado=None,
            asignacion_ultima_tarea=None,
            mesa_categoria_asignada=None,
            distrito_afin=None,
            puntaje_scoring_troll=0,
        )
        MesaCategoria.objects.all().update(
            percentil=None,
            orden_de_llegada=None,
            coeficiente_para_orden_de_carga=None,
            cant_fiscales_asignados=0,
            cant_asignaciones_realizadas=0,
            status=MesaCategoria.STATUS.sin_cargar,
        )
