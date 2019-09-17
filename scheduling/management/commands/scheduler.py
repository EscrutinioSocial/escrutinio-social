import time
import structlog

from django.core.management.base import BaseCommand
from constance import config

from scheduling.scheduler import scheduler
from adjuntos.management.commands.consolidar_identificaciones_y_cargas import consolidador

logger = structlog.get_logger('scheduler')


class Command(BaseCommand):
    help = "Scheduler asincrónico. Encola mesas-categorías con fotos para identificar."

    def handle(self, *args, **options):
        while True:
            consolidador(ejecutado_desde='Scheduler')
            cant_tareas = scheduler()
            logger.debug(
                'Encolado',
                cargas=cant_tareas
            )
            time.sleep(config.PAUSA_SCHEDULER)
