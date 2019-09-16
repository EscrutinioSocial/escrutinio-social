from django.core.management.base import BaseCommand
from constance import config
from scheduling.scheduler import scheduler, count_active_sessions
import time
import structlog


logger = structlog.get_logger('scheduler')


class Command(BaseCommand):
    help = "Scheduler asincrónico. Encola mesas-categorías con fotos para identificar."

    def handle(self, *args, **options):
        while True:
            cant_tareas = scheduler()
            logger.debug(
                'Encolado',
                cargas=cant_tareas
            )
            time.sleep(config.PAUSA_SCHEDULER)
