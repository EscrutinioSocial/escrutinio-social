import time
import structlog

from django.core.management.base import BaseCommand
from constance import config
from sentry_sdk import capture_message
from scheduling.scheduler import scheduler
from adjuntos.management.commands.consolidar_identificaciones_y_cargas import consolidador

logger = structlog.get_logger('scheduler')


class Command(BaseCommand):
    help = "Scheduler asincrónico. Encola mesas-categorías con fotos para identificar."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cant_elem_consolidador",
            type=int, default=100,
            help="Cantidad de elementos a procesar por corrida del consolidador (None es sin límite, default %(default)s)."
        )
        parser.add_argument(
            "--cant_rondas_antes_de_reconstruir_la_cola",
            type=int, default=5,
            help="Cantidad de rondas de consolidación antes de vaciar la cola (default %(default)s)."
        )

    def handle(self, *args, **options):
        ronda_consolidador = 0
        while True:
            consolidador(cant_por_iteracion=options['cant_elem_consolidador'], ejecutado_desde='Scheduler')
            ronda_consolidador += 1
            if ronda_consolidador == options['cant_rondas_antes_de_reconstruir_la_cola']:
                ronda_consolidador = 0
                reconstruir_la_cola = True
            else:
                reconstruir_la_cola = False
            try:
                (cant_tareas, cant_cargas, cant_ident) = scheduler(reconstruir_la_cola)
                logger.debug(
                    'Encolado',
                    tareas=cant_tareas,
                    cargas=cant_cargas,
                    identificaciones=cant_ident,
                    reconstruir_la_cola=reconstruir_la_cola,
                )
            except Exception as e:
                # Logueamos la excepción y continuamos.
                capture_message(
                    f"""
                    Excepción {e} en el scheduler.
                    """
                )
                logger.error('Scheduler',
                    error=str(e)
                )
            time.sleep(config.PAUSA_SCHEDULER)
