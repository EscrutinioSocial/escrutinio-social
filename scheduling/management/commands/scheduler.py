import time
import structlog

from django.core.management.base import BaseCommand
from constance import config

from scheduling.scheduler import scheduler
from adjuntos.management.commands.consolidar_identificaciones_y_cargas import consolidador

logger = structlog.get_logger('scheduler')


class Command(BaseCommand):
    help = "Scheduler asincrónico. Encola mesas-categorías con fotos para identificar."

    def add_arguments(self, parser):
        parser.add_argument("--cant_elem_consolidador",
            type=int, default=100,
            help="Cantidad de elementos a procesar por corrida del consolidador (None es sin límite, default %(default)s)."
        )

    def handle(self, *args, **options):
        while True:
            consolidador(cant_por_iteracion=options['cant_elem_consolidador'], ejecutado_desde='Scheduler')
            (cant_tareas, cant_cargas, cant_ident) = scheduler()
            logger.debug(
                'Encolado',
                tareas=cant_tareas,
                cargas=cant_cargas,
                identificaciones=cant_ident
            )
            time.sleep(config.PAUSA_SCHEDULER)
