import pytest
import os

from django.contrib.auth.models import Group
from django.http import Http404
from django.conf import settings

from adjuntos.csv_import import (ColumnasInvalidasError, CSVImporter, DatosInvalidosError,
                                 PermisosInvalidosError)
from elecciones.models import Carga, VotoMesaReportado
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
CATEGORIAS = [('Presidente y vice', True), ('Gobernador y vice', True),
              ('Intendentes, Concejales y Consejeros Escolares', False), ('Legisladores Provinciales', True),
              ('Senadores Nacionales', True), ('Diputados Nacionales', True),
              ('Senadores Provinciales', True), ('Diputados Provinciales', True)]


def test_validar_csv_fiscal_no_encontrado(db):
    user = UserFactory()
    with pytest.raises(PermisosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_negativos.csv', user).validar()
    assert 'Fiscal no encontrado' in str(e.value)


def test_validar_csv_fiscal_sin_permisos_suficientes(db):
    user = UserFactory()
    FiscalFactory(user=user)
    Group.objects.create(name='unidades basicas')
    g_visualizadores = Group.objects.create(name='visualizadores')
    user.groups.add(g_visualizadores)
    with pytest.raises(PermisosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_negativos.csv', user).validar()
    assert 'Su usuario no tiene los permisos necesarios' in str(e.value)


@pytest.fixture()
def usr_unidad_basica(db):
    user = UserFactory()
    FiscalFactory(user=user)
    for nombre in ['unidades basicas', 'visualizadores']:
        g = Group.objects.create(name=nombre)
    g_unidades_basicas = Group.objects.get(name='unidades basicas')
    user.groups.add(g_unidades_basicas)
    return user


def test_validar_csv_faltan_columnas(usr_unidad_basica):
    with pytest.raises(ColumnasInvalidasError):
        CSVImporter(PATH_ARCHIVOS_TEST + 'faltan_columnas.csv', usr_unidad_basica).validar()


def test_validar_csv_columnas_duplicadas(usr_unidad_basica):
    with pytest.raises(ColumnasInvalidasError):
        CSVImporter(PATH_ARCHIVOS_TEST + 'columnas_duplicadas.csv', usr_unidad_basica).validar()


def test_validar_csv_mesas_invalidas(db, usr_unidad_basica):
    with pytest.raises(DatosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'mesas_invalidas.csv', usr_unidad_basica).validar()
    assert 'No existe mesa' in str(e.value)


def test_procesar_csv_categorias_faltantes_en_archivo(db, usr_unidad_basica):
    d1 = DistritoFactory(numero=1)
    s1 = SeccionFactory(numero=50, distrito=d1)
    c1 = CircuitoFactory(numero='2', seccion=s1)
    m = MesaFactory(numero='4012', lugar_votacion__circuito=c1, electores=100, circuito=c1)
    o2 = OpcionFactory(orden=3, codigo='A')
    o3 = OpcionFactory(orden=2, codigo='B')
    votos = OpcionFactory(orden=0, **settings.OPCION_TOTAL_VOTOS)
    sobres = OpcionFactory(orden=1, codigo='0', **settings.OPCION_TOTAL_SOBRES)
    c = CategoriaFactory(opciones=[o2, o3, votos, sobres], nombre='Otra categoria')
    CategoriaOpcionFactory(categoria=c, opcion__orden=1, prioritaria=True)
    MesaCategoriaFactory(mesa=m, categoria=c)

    with pytest.raises(DatosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_negativos.csv', usr_unidad_basica).procesar()
    assert 'Faltan datos en el archivo de la siguiente categoría' in str(e.value)


@pytest.fixture()
def carga_inicial(db):
    d1 = DistritoFactory(numero=1)
    s1 = SeccionFactory(numero=50, distrito=d1)
    circ = CircuitoFactory(numero='2', seccion=s1)
    # crear las opciones para votos y sobres
    votos = OpcionFactory(orden=0, codigo='0', **settings.OPCION_TOTAL_VOTOS)
    sobres = OpcionFactory(orden=1, codigo='0', **settings.OPCION_TOTAL_SOBRES)
    o1 = OpcionFactory(orden=3, codigo='A')
    o2 = OpcionFactory(orden=2, codigo='B')
    categorias = []
    for categoria in CATEGORIAS:
        categoria_bd = CategoriaFactory(nombre=categoria[0])
        categorias.append(categoria_bd)
        CategoriaOpcionFactory(categoria=categoria_bd, opcion__orden=1, prioritaria=categoria[1], opcion=o1)
        CategoriaOpcionFactory(categoria=categoria_bd, opcion__orden=1, prioritaria=categoria[1], opcion=o2)
        if categoria[0] == 'Presidente y vice':
            # Les ajusto el orden.
            votos = categoria_bd.get_opcion_total_votos()
            votos.orden = 1
            votos.save()
            sobres = categoria_bd.get_opcion_total_sobres()
            sobres.orden = 1
            sobres.save()

            # Las hago prioritarias.
            votos_cat_opcion = categoria_bd.categoriaopcion_set.get(opcion=votos)
            votos_cat_opcion.prioritaria = True
            votos_cat_opcion.save()
            sobres_cat_opcion = categoria_bd.categoriaopcion_set.get(opcion=sobres)
            sobres_cat_opcion.prioritaria = True
            sobres_cat_opcion.save()
    MesaFactory(numero='4012', lugar_votacion__circuito=circ, electores=100, circuito=circ,
                categorias=categorias)


def test_procesar_csv_resultados_negativos(db, usr_unidad_basica, carga_inicial):
    with pytest.raises(DatosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_negativos.csv', usr_unidad_basica).procesar()
    assert 'Los resultados deben ser números positivos' in str(e.value)


def test_procesar_csv_opciones_no_encontradas(db, usr_unidad_basica, carga_inicial):
    with pytest.raises(DatosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'opciones_invalidas.csv', usr_unidad_basica).procesar()
    assert 'El número de lista C no fue encontrado' in str(e.value)


def test_procesar_csv_informacion_valida_genera_resultados(db, usr_unidad_basica, carga_inicial):
    CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_ok.csv', usr_unidad_basica).procesar()
    carga_total = Carga.objects.filter(tipo=Carga.TIPOS.total).all()
    totales = len([categoria for categoria in CATEGORIAS if not categoria[1]])
    assert len(carga_total) == totales
    for total in carga_total:
        assert total.origen == 'csv'
    votos_carga_total = VotoMesaReportado.objects.filter(carga__in=carga_total).all()
    # ya que hay dos opciones y 1 categoria no prioritaria
    assert len(votos_carga_total) == 2
    carga_parcial = Carga.objects.filter(tipo=Carga.TIPOS.parcial).all()
    parciales = len(CATEGORIAS) - totales
    assert len(carga_parcial) == parciales
    for parcial in carga_parcial:
        assert parcial.origen == 'csv'
    votos_carga_parcial = VotoMesaReportado.objects.filter(carga__in=carga_parcial).all()
    # ya que hay dos opciones y 7 categorias prioritarias
    assert len(votos_carga_parcial) == 14


def test_procesar_csv_informacion_valida_con_metadata_genera_resultados(db, usr_unidad_basica,
                                                                        carga_inicial):
    CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_metadata_ok.csv', usr_unidad_basica).procesar()
    carga_total = Carga.objects.filter(tipo=Carga.TIPOS.total).all()
    totales = len([categoria for categoria in CATEGORIAS if not categoria[1]])
    assert len(carga_total) == totales
    for total in carga_total:
        assert total.origen == 'csv'
    votos_carga_total = VotoMesaReportado.objects.filter(carga__in=carga_total).all()
    # ya que hay dos opciones y 1 categoria no prioritaria
    assert len(votos_carga_total) == 2
    carga_parcial = Carga.objects.filter(tipo=Carga.TIPOS.parcial).all()
    parciales = len(CATEGORIAS) - totales
    assert len(carga_parcial) == parciales
    for parcial in carga_parcial:
        assert parcial.origen == 'csv'
    votos_carga_parcial = VotoMesaReportado.objects.filter(carga__in=carga_parcial).all()
    # ya que hay dos opciones y 7 categorias prioritarias y 2 opciones de metadata
    assert len(votos_carga_parcial) == 16
