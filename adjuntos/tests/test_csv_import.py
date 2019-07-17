import pytest
import os

from django.http import Http404

from adjuntos.csv_import import ColumnasInvalidasError, CSVImporter, DatosInvalidosError
from elecciones.models import Carga
from elecciones.tests.factories import (
    DistritoFactory,
    SeccionFactory,
    CircuitoFactory,
    MesaFactory,
    CategoriaFactory,
    OpcionFactory,
    CategoriaOpcionFactory,
    MesaCategoriaFactory,
    FiscalFactory,
    UserFactory)

PATH_ARCHIVOS_TEST = os.path.dirname(os.path.abspath(__file__)) + '/archivos/'
CATEGORIAS = [('Presidente y vice,Gobernador y vice', True),
              ('Intendentes, Concejales y Consejeros Escolares', False), ('Legisladores Provinciales', True),
              ('Senadores Nacionales', True), ('Diputados Nacionales', True),
              ('Senadores Provinciales', True), ('Diputados Provinciales', True)]


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
    CategoriaOpcionFactory(categoria=c, opcion__orden=1, prioritaria=True)
    MesaCategoriaFactory(mesa=m, categoria=c)
    with pytest.raises(DatosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_negativos.csv', user).procesar()
    assert 'Faltan datos en el archivo de la siguiente categoria' in str(e.value)


@pytest.fixture()
def carga_inicial(db):
    d1 = DistritoFactory(numero=1)
    s1 = SeccionFactory(numero=50, distrito=d1)
    circ = CircuitoFactory(numero='2', seccion=s1)
    o1 = OpcionFactory(orden=3, codigo='A')
    o2 = OpcionFactory(orden=2, codigo='B')
    categorias = []
    for categoria in CATEGORIAS:
        categoria_bd = CategoriaFactory(nombre=categoria[0])
        categorias.append(categoria_bd)
        CategoriaOpcionFactory(categoria=categoria_bd, opcion__orden=1, prioritaria=categoria[1], opcion=o1)
        CategoriaOpcionFactory(categoria=categoria_bd, opcion__orden=1, prioritaria=categoria[1], opcion=o2)
    MesaFactory(numero='4012', lugar_votacion__circuito=circ, electores=100, circuito=circ,
                categorias=categorias)


def test_procesar_csv_resultados_negativos(db, carga_inicial):
    user = UserFactory()
    FiscalFactory(user=user)
    with pytest.raises(DatosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_negativos.csv', user).procesar()
    assert 'Los resultados deben ser números positivos' in str(e.value)


def test_procesar_csv_opciones_no_encontradas(db, carga_inicial):
    user = UserFactory()
    FiscalFactory(user=user)
    with pytest.raises(DatosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'opciones_invalidas.csv', user).procesar()
    assert 'El número de lista C no fue encontrado' in str(e.value)


def test_procesar_csv_informacion_valida_genera_resultados(db, carga_inicial):
    user = UserFactory()
    FiscalFactory(user=user)
    CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_ok.csv', user).procesar()
    carga_total = Carga.objects.filter(tipo=Carga.TIPOS.total).all()
    totales = len([categoria for categoria in CATEGORIAS if not categoria[1]])
    assert len(carga_total) == totales
    for total in carga_total:
        assert total.origen == 'csv'
    carga_parcial = Carga.objects.filter(tipo=Carga.TIPOS.parcial).all()
    assert len(carga_parcial) == len(CATEGORIAS) - totales
    for parcial in carga_parcial:
        assert parcial.origen == 'csv'
