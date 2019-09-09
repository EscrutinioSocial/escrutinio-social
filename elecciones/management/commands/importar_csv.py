from decimal import Decimal
from django.conf import settings
from django.db.utils import IntegrityError
from csv import DictReader
from django.db import transaction
from adjuntos.csv_import import (ColumnasInvalidasError, CSVImporter, DatosInvalidosError,
                                 PermisosInvalidosError)
from fiscales.models import Fiscal
from .basic_command import BaseCommand


class Command(BaseCommand):
    """
    Importar CSV
    """
    help = "Importar CSV."

    def handle(self, *args, **options):
        super().handle(*args, **options)

        usr = Fiscal.objects.all().first()
        cant_mesas_ok, cant_mesas_parcialmente_ok, errores = CSVImporter(self.CSV, usr.user).procesar()
        print(f"{cant_mesas_ok} mesas ok, {cant_mesas_parcialmente_ok} mesas parcialmente ok. "
        	f"Errores: {errores}"
        )