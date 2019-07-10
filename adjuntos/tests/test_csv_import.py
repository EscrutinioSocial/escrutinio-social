import pytest
import os

from adjuntos.csv_import import ColumnasInvalidasError, CSVImporter, DatosInvalidosError

PATH_ARCHIVOS_TEST = os.path.dirname(os.path.abspath(__file__)) + '/archivos/'


def test_validar_csv_faltan_columnas():
    with pytest.raises(ColumnasInvalidasError):
        CSVImporter(PATH_ARCHIVOS_TEST + 'faltan_columnas.csv', None).validar()


def test_validar_csv_columnas_duplicadas():
    with pytest.raises(ColumnasInvalidasError):
        CSVImporter(PATH_ARCHIVOS_TEST + 'columnas_duplicadas.csv', None).validar()


def test_validar_csv_mesas_invalidas(db):
    with pytest.raises(DatosInvalidosError):
        CSVImporter(PATH_ARCHIVOS_TEST + 'mesas_invalidas.csv', None).validar()
