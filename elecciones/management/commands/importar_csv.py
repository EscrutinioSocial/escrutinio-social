from adjuntos.csv_import import CSVImporter
from adjuntos.models import CSVTareaDeImportacion
from fiscales.models import Fiscal
from django.core.management.base import BaseCommand
from django.db import transaction
from threading import Thread
from pathlib import Path
import threading
import logging
import structlog
import time


class Command(BaseCommand):
    """
    Importador de CSV
    """
    help = "Importador de CSV."

    def handle(self, *args, **options):

        self.debug = options['debug']
        self.usr = Fiscal.objects.all().first()
        self.logger = logging.getLogger('csv_import')
        self.espera_tarea = options['espera_tarea']

        if options['file']:
            self.importar_ahora(options['file'])
        elif options['crear_tarea']:
            self.crear_tarea(options['crear_tarea'])
        else:
            self.lanzar_threads(options['cant_workers'])

    def add_arguments(self, parser):

        parser.add_argument("--debug", action="store_true",
                            dest="debug",
                            default=False,
                            help="Habilita el modo debug."
                            )

        parser.add_argument("--file", type=str, default=None,
                            help="Lee el archivo parámetro en el momento."
                            )

        parser.add_argument("--crear_tarea", type=str, default=None,
                            help="Crea una tarea para el archivo parámetro."
                            )

        parser.add_argument("--cant_workers", type=int,
                            default=5,
                            help="Cantidad de workers que forkea (default %(default)s)."
                            )

        parser.add_argument("--espera_tarea", type=int,
                            default=5,
                            help="Cantidad de segundos que duerme para conseguir una tarea (default %(default)s)."
                            )

    def importar_ahora(self, file):
        # cant_mesas_ok, cant_mesas_parcialmente_ok, errores = CSVImporter(self.CSV, usr.user).procesar()
        # print(f"{cant_mesas_ok} mesas ok, {cant_mesas_parcialmente_ok} mesas parcialmente ok. "
        #   f"Errores: {errores}"
        # )
        csvimporter = CSVImporter(Path(file), self.usr.user, self.debug)

        errores = csvimporter.procesar_parcialmente()
        for cant_mesas_ok, cant_mesas_parcialmente_ok, error in errores:
            print("Error: ", error)

        print(f"{cant_mesas_ok} mesas ok, {cant_mesas_parcialmente_ok} mesas parcialmente ok. "
              # f"Errores: {error}"
              )

    def crear_tarea(self, archivo):
        CSVTareaDeImportacion.objects.create(
            csv_file=archivo,
            fiscal=self.usr
        )

    @transaction.atomic
    def tomar_tarea(self):
        tarea = CSVTareaDeImportacion.objects.select_for_update(
            skip_locked=True
        ).filter(
            status=CSVTareaDeImportacion.STATUS.pendiente
        ).first()
        if tarea:
            tarea.cambiar_status(CSVTareaDeImportacion.STATUS.en_progreso)
        return tarea

    def worker_import_file(self, tarea):
        """
        Hace la importación de un archivo propiamente dicha.
        """
        csvimporter = CSVImporter(Path(tarea.csv_file.name), self.usr.user, self.debug)
        errores = csvimporter.procesar_parcialmente()
        i = 0
        if not tarea.errores:
            tarea.errores = ''
        for cant_mesas_ok, cant_mesas_parcialmente_ok, error in errores:
            tarea.errores = tarea.errores + error
            i += 1
            if i == 20:
                # Cada 20 errores grabamos.
                i = 0
                tarea.save_errores()

        # Si quedaron errores sin grabar los grabamos:
        if i > 0:
            tarea.save_errores()

        tarea.fin_procesamiento(cant_mesas_ok, cant_mesas_parcialmente_ok)
        self.logger.info("[%d] Tarea terminada: %s", self.thread_local.worker_id, tarea)

    def wait_and_process_task(self):
        """
        Espera a que haya una tarea, la toma y la procesa.
        """
        # Tomo una tarea.
        tarea = None
        while not tarea and not self.finalizar:
            tarea = self.tomar_tarea()
            if not tarea:
                time.sleep(self.espera_tarea)

        if not self.finalizar:
            self.logger.info("[%d] Tarea seleccionada: %s", self.thread_local.worker_id, tarea)
            self.worker_import_file(tarea)

    def csv_import_worker(self, thread_id):
        """
        Cicla procesando una tarea tras otra.
        """
        self.thread_local.worker_id = thread_id
        self.logger.info("[%d] Worker listo.", self.thread_local.worker_id)
        while not self.finalizar:
            self.wait_and_process_task()
        self.logger.info("[%d] Worker finalizado.", self.thread_local.worker_id)

    def lanzar_threads(self, cant_workers):
        self.finalizar = False
        self.thread_local = threading.local()
        threads = []
        for i in range(cant_workers):
            t = Thread(target=self.csv_import_worker, args=(i,), daemon=False)
            t.start()
            threads.append(t)

        # Me quedo esperando a que terminen procesando Ctrl-C.
        while not self.finalizar:
            try:
                time.sleep(60)
            except KeyboardInterrupt:
                self.finalizar = True
                print(self.style.SUCCESS("Finalizando. Presionar de nuevo para terminar ahora."))
                for thread in threads:
                    thread.join()
