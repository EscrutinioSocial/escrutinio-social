import os

import pytest
from django.conf import settings
from django.contrib.auth.models import Group

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
              ('Intendentes, Concejales y Consejeros Escolares', False),
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
    o2 = OpcionFactory(orden=3, codigo='Todes')
    o3 = OpcionFactory(orden=2, codigo='Juntos')
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

    # Creamos los partidos.
    fdt = OpcionFactory(orden=3, codigo='FdT')
    jpc = OpcionFactory(orden=2, codigo='JpC')
    c2019 = OpcionFactory(orden=4, codigo='C2019')

    categorias = []
    for categoria, prioritaria in CATEGORIAS:
        categoria_bd = CategoriaFactory(nombre=categoria)
        categorias.append(categoria_bd)
        CategoriaOpcionFactory(categoria=categoria_bd, opcion__orden=1, prioritaria=prioritaria, opcion=fdt)
        CategoriaOpcionFactory(categoria=categoria_bd, opcion__orden=1, prioritaria=prioritaria, opcion=jpc)
        if categoria == 'Presidente y vice':
            CategoriaOpcionFactory(categoria=categoria_bd, opcion__orden=1, prioritaria=False, opcion=c2019)
            # Adecuamos las opciones prioritarias.
            total_votos = categoria_bd.get_opcion_total_votos()
            total_votos_cat_opcion = categoria_bd.categoriaopcion_set.get(opcion=total_votos)
            total_votos_cat_opcion.prioritaria = True
            total_votos_cat_opcion.save()

            blancos = categoria_bd.get_opcion_total_sobres()
            blancos_cat_opcion = categoria_bd.categoriaopcion_set.get(opcion=blancos)
            blancos_cat_opcion.prioritaria = True
            blancos_cat_opcion.save()

            nulos = categoria_bd.get_opcion_nulos()
            nulos_cat_opcion = categoria_bd.categoriaopcion_set.get(opcion=nulos)
            nulos_cat_opcion.prioritaria = True
            nulos_cat_opcion.save()

    MesaFactory(numero='4012', lugar_votacion__circuito=circ, electores=100, circuito=circ,
                categorias=categorias)


def test_procesar_csv_resultados_negativos(db, usr_unidad_basica, carga_inicial):
    with pytest.raises(DatosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_negativos.csv', usr_unidad_basica).procesar()
    assert 'Los resultados deben ser números positivos' in str(e.value)


def test_procesar_csv_opciones_no_encontradas(db, usr_unidad_basica, carga_inicial):
    with pytest.raises(DatosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'opciones_invalidas.csv', usr_unidad_basica).procesar()
    assert 'El número de lista C2019 no fue encontrado' in str(e.value)


def test_falta_total_de_votos(db, usr_unidad_basica, carga_inicial):
    with pytest.raises(DatosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'falta_total_votos.csv', usr_unidad_basica).procesar()
    assert 'Falta el reporte de total de votantes para la mesa' in str(e.value)


def test_procesar_csv_informacion_valida_genera_resultados(db, usr_unidad_basica, carga_inicial):
    CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_ok.csv', usr_unidad_basica).procesar()
    cargas_totales = Carga.objects.filter(tipo=Carga.TIPOS.total)

    assert cargas_totales.count() == len(CATEGORIAS)
    for total in cargas_totales:
        assert total.origen == 'csv'

    votos_carga_total = VotoMesaReportado.objects.filter(carga__in=cargas_totales).all()
    # XXX Ver cuántos deberían ser.
    assert len(votos_carga_total) == 2

    cargas_parciales = Carga.objects.filter(tipo=Carga.TIPOS.parcial)
    cant_parciales = len(CATEGORIAS) - totales
    assert cargas_parciales.count() == cant_parciales

    for parcial in cargas_parciales:
        assert parcial.origen == 'csv'

    votos_carga_parcial = VotoMesaReportado.objects.filter(carga__in=cargas_parciales).all()
    # Ya que hay dos opciones + total de votantes x 6 categorias prioritarias
    assert len(votos_carga_parcial) == 18


def test_procesar_csv_informacion_valida_copia_parciales_a_totales(db, usr_unidad_basica, carga_inicial):
    CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_copia_parciales_a_totales.csv',
                usr_unidad_basica).procesar()
    cargas_totales = Carga.objects.filter(tipo=Carga.TIPOS.total).all()
    cargas_parciales = Carga.objects.filter(tipo=Carga.TIPOS.parcial).all()

    # Todo lo que está en carga total también está en carga parcial para la misma categoría.
    for carga_parcial in cargas_parciales:
        cargas_totales_misma_mc = cargas_totales.filter(mesa_categoria=carga_parcial.mesa_categoria)
        if cargas_totales_misma_mc.count() == 0:
            continue
        carga_total_misma_mc = cargas_totales_misma_mc.first()
        for voto in carga_parcial.reportados.all():
            assert VotoMesaReportado.objects.filter(carga=carga_total_misma_mc, votos=voto.votos,
                                                    opcion=voto.opcion).exists()
