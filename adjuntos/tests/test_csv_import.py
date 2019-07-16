import pytest
import os

from django.http import Http404

from adjuntos.csv_import import ColumnasInvalidasError, CSVImporter, DatosInvalidosError
from elecciones.tests.factories import DistritoFactory, SeccionFactory, CircuitoFactory, MesaFactory, CategoriaFactory, \
    OpcionFactory, CategoriaOpcionFactory, MesaCategoriaFactory, FiscalFactory, UserFactory

PATH_ARCHIVOS_TEST = os.path.dirname(os.path.abspath(__file__)) + '/archivos/'


def test_validar_csv_faltan_columnas():
    with pytest.raises(ColumnasInvalidasError):
        CSVImporter(PATH_ARCHIVOS_TEST + 'faltan_columnas.csv', None).validar()


def test_validar_csv_columnas_duplicadas():
    with pytest.raises(ColumnasInvalidasError):
        CSVImporter(PATH_ARCHIVOS_TEST + 'columnas_duplicadas.csv', None).validar()


def test_validar_csv_mesas_invalidas(db):
    with pytest.raises(DatosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'mesas_invalidas.csv', None).validar()
    assert 'No existe mesa' in str(e.value)


def test_procesar_csv_fiscal_no_encontrado(db):
    d1 = DistritoFactory(numero=1)
    user = UserFactory()
    s1 = SeccionFactory(numero=50, distrito=d1)
    c1 = CircuitoFactory(numero='2', seccion=s1)
    m = MesaFactory(numero='4012', lugar_votacion__circuito=c1, electores=100, circuito=c1)
    o2 = OpcionFactory(orden=3, codigo='A')
    o3 = OpcionFactory(orden=2, codigo='B')
    c = CategoriaFactory(opciones=[o2, o3], nombre='Presidente y vice')
    CategoriaOpcionFactory(categoria=c, opcion__orden=1, prioritaria=True)
    MesaCategoriaFactory(mesa=m, categoria=c)
    with pytest.raises(Http404) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_negativos.csv', user).procesar()


def test_procesar_csv_categorias_faltantes_en_archivo(db):
    d1 = DistritoFactory(numero=1)
    user = UserFactory()
    FiscalFactory(user=user)
    s1 = SeccionFactory(numero=50, distrito=d1)
    c1 = CircuitoFactory(numero='2', seccion=s1)
    m = MesaFactory(numero='4012', lugar_votacion__circuito=c1, electores=100, circuito=c1)
    o2 = OpcionFactory(orden=3, codigo='A')
    o3 = OpcionFactory(orden=2, codigo='B')
    c = CategoriaFactory(opciones=[o2, o3], nombre='Presidente y vice')
    o1 = CategoriaOpcionFactory(categoria=c, opcion__orden=1, prioritaria=True)
    MesaCategoriaFactory(mesa=m, categoria=c)
    with pytest.raises(DatosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_negativos.csv', user).procesar()
    assert 'Faltan datos en el archivo de la siguiente categoria' in str(e.value)
