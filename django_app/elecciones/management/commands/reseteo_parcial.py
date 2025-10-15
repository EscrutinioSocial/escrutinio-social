from django.db.utils import IntegrityError
from django.db import transaction, connection
from django.core.management.base import BaseCommand
from adjuntos.models import Attachment, PreIdentificacion, CSVTareaDeImportacion
from problemas.models import Problema
from elecciones.models import (VotoMesaReportado, Carga, MesaCategoria)
from fiscales.models import Fiscal
from scheduling.models import ColaCargasPendientes

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
        tablas_a_resetear_secuencias = []
        Attachment.objects.all().delete()
        tablas_a_resetear_secuencias.append('adjuntos_attachment')
        CSVTareaDeImportacion.objects.all().delete()
        tablas_a_resetear_secuencias.append('adjuntos_csvtareadeimportacion')
        PreIdentificacion.objects.all().delete()
        tablas_a_resetear_secuencias.append('adjuntos_preidentificacion')
        Problema.objects.all().delete()
        tablas_a_resetear_secuencias.append('problemas_problema')
        tablas_a_resetear_secuencias.append('problemas_reportedeproblema')
        VotoMesaReportado.objects.all().delete()
        tablas_a_resetear_secuencias.append('elecciones_votomesareportado')
        Carga.objects.all().delete()
        tablas_a_resetear_secuencias.append('elecciones_carga')
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
        ColaCargasPendientes.objects.all().delete()
        tablas_a_resetear_secuencias.append('scheduling_colacargaspendientes')

        with connection.cursor() as cursor:
            for tabla in tablas_a_resetear_secuencias:
                cursor.execute(f'SELECT setval(pg_get_serial_sequence(\'"{tabla}"\',\'id\'), coalesce(max("id"), 1), max("id") IS NOT null) FROM "{tabla}";')
