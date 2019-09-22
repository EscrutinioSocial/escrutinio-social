from adjuntos.csv_import import (CSVImporter)
from fiscales.models import Fiscal
from .basic_command import BaseCommand


class Command(BaseCommand):
    """
    Importar CSV
    """
    help = "Importar CSV."

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument("--debug", action="store_true",
                            dest="debug",
                            default=False,
                            help="Habilita el modo debug."
                            )

    def handle(self, *args, **options):
        super().handle(*args, **options)

        debug = options['debug']

        usr = Fiscal.objects.all().first()
        # cant_mesas_ok, cant_mesas_parcialmente_ok, errores = CSVImporter(self.CSV, usr.user).procesar()
        # print(f"{cant_mesas_ok} mesas ok, {cant_mesas_parcialmente_ok} mesas parcialmente ok. "
        #	f"Errores: {errores}"
        # )
        csvimporter = CSVImporter(self.CSV, usr.user, debug)

        errores = csvimporter.procesar_parcialmente()
        for cant_mesas_ok, cant_mesas_parcialmente_ok, error in errores:
            print("Error: ", error)

        print(f"{cant_mesas_ok} mesas ok, {cant_mesas_parcialmente_ok} mesas parcialmente ok. "
              # f"Errores: {error}"
              )
