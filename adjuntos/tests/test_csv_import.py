import os

import pytest
from django.conf import settings
from django.contrib.auth.models import Group

from adjuntos.csv_import import (ColumnasInvalidasError, CSVImporter, DatosInvalidosError,
                                 PermisosInvalidosError)
from elecciones.models import Carga, VotoMesaReportado, CategoriaOpcion, Opcion
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
              ('Intendente, Concejales y Consejeros Escolares', False),
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
    assert Carga.objects.count() == 0


def test_validar_csv_columnas_duplicadas(usr_unidad_basica):
    with pytest.raises(ColumnasInvalidasError):
        CSVImporter(PATH_ARCHIVOS_TEST + 'columnas_duplicadas.csv', usr_unidad_basica).validar()
    assert Carga.objects.count() == 0


def test_validar_csv_mesas_invalidas(db, usr_unidad_basica):
    ok, errores = CSVImporter(PATH_ARCHIVOS_TEST + 'mesas_invalidas.csv', usr_unidad_basica).procesar()
    assert 'No existe mesa' in errores
    assert Carga.objects.count() == 0


def test_procesar_csv_categorias_faltantes_en_archivo(db, usr_unidad_basica):
    d1 = DistritoFactory(numero=1)
    s1 = SeccionFactory(numero=50, distrito=d1)
    c1 = CircuitoFactory(numero='2', seccion=s1)
    m = MesaFactory(numero='4012', lugar_votacion__circuito=c1, electores=100, circuito=c1)
    o2 = OpcionFactory(orden=3, codigo='Todes')
    o3 = OpcionFactory(orden=2, codigo='Juntos')
    c = CategoriaFactory(opciones=[o2, o3], nombre='Otra categoria')
    CategoriaOpcionFactory(categoria=c, opcion__orden=1, prioritaria=True)
    MesaCategoriaFactory(mesa=m, categoria=c)

    with pytest.raises(DatosInvalidosError) as e:
        CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_negativos.csv', usr_unidad_basica).procesar()
    assert 'Faltan datos en el archivo de la siguiente categoría' in str(e.value)
    assert Carga.objects.count() == 0


@pytest.fixture()
def carga_inicial(db):
    d1 = DistritoFactory(numero=1)
    s1 = SeccionFactory(numero=50, distrito=d1)
    circ = CircuitoFactory(numero='2', seccion=s1)

    # Creamos los partidos.
    fdt = OpcionFactory(orden=3, codigo='FdT', nombre='FdT', partido__nombre='FpT')
    jpc = OpcionFactory(orden=2, codigo='JpC', nombre='JpC', partido__nombre='JpC')
    c2019 = OpcionFactory(orden=4, codigo='C2019', nombre='C2019', partido__nombre='C2019')

    categorias = []
    for categoria, prioritaria in CATEGORIAS:
        categoria_bd = CategoriaFactory(nombre=categoria)

        # La factory las crea con unas opciones que hacen ruido en estos tests.
        for nombre in ['opc1', 'opc2', 'opc3', 'opc4']:
            opcion = Opcion.objects.get(nombre=nombre)
            opcion.delete()

        categorias.append(categoria_bd)
        CategoriaOpcionFactory(categoria=categoria_bd, prioritaria=prioritaria, opcion=fdt)
        CategoriaOpcionFactory(categoria=categoria_bd, prioritaria=prioritaria, opcion=jpc)
        if categoria == 'Presidente y vice':
            CategoriaOpcionFactory(categoria=categoria_bd, prioritaria=False, opcion=c2019)
        if prioritaria:
            # Adecuamos las opciones prioritarias.
            total_votos = Opcion.total_votos()
            total_votos_cat_opcion = categoria_bd.categoriaopcion_set.get(opcion=total_votos)
            total_votos_cat_opcion.prioritaria = True
            total_votos_cat_opcion.save()

            blancos = Opcion.blancos()
            blancos_cat_opcion = categoria_bd.categoriaopcion_set.get(opcion=blancos)
            blancos_cat_opcion.prioritaria = True
            blancos_cat_opcion.save()

            nulos = Opcion.nulos()
            nulos_cat_opcion = categoria_bd.categoriaopcion_set.get(opcion=nulos)
            nulos_cat_opcion.prioritaria = True
            nulos_cat_opcion.save()

    MesaFactory(numero='4012', lugar_votacion__circuito=circ, electores=100, circuito=circ,
                categorias=categorias)


def test_procesar_csv_resultados_negativos(db, usr_unidad_basica, carga_inicial):
    ok, errores = CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_negativos.csv', usr_unidad_basica).procesar()
    assert ok is False
    assert 'Los resultados deben ser números enteros positivos' in errores
    assert Carga.objects.count() == 0


def test_procesar_csv_opciones_no_encontradas(db, usr_unidad_basica, carga_inicial):
    ok, errores = CSVImporter(PATH_ARCHIVOS_TEST + 'opciones_invalidas.csv', usr_unidad_basica).procesar()
    assert ok is False
    assert 'El número de lista C2019 no fue encontrado' in errores
    assert Carga.objects.count() == 0


def test_falta_total_de_votos(db, usr_unidad_basica, carga_inicial):
    ok, errores = CSVImporter(PATH_ARCHIVOS_TEST + 'falta_total_votos.csv', usr_unidad_basica).procesar()
    assert ok is False
    assert "Faltan las opciones: ['total de votos']." in errores
    assert Carga.objects.count() == 0


def test_procesar_csv_informacion_valida_genera_resultados(db, usr_unidad_basica, carga_inicial):
    ok, errores = CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_ok.csv', usr_unidad_basica).procesar()
    assert ok is True
    cargas_totales = Carga.objects.filter(tipo=Carga.TIPOS.total)

    # Debería haber 2 cargas total: Int (que no es prio), y presi, que es prio pero tiene
    # además opción no prioritaria.
    assert cargas_totales.count() == 2
    for total in cargas_totales:
        assert total.origen == 'csv'

    votos_carga_total = VotoMesaReportado.objects.filter(carga__in=cargas_totales).all()
    # Cat Int tiene 2 partidos + total + blancos + nulos + sobres = 6
    # Cat Pres tiene 3 partidos + total + blancos + nulos + sobres = 7
    assert votos_carga_total.count() == 13

    cargas_parciales = Carga.objects.filter(tipo=Carga.TIPOS.parcial)
    # Hay una sola categoría no prioritaria.
    assert cargas_parciales.count() == len(CATEGORIAS) - 1

    for parcial in cargas_parciales:
        assert parcial.origen == 'csv'

    votos_carga_parcial = VotoMesaReportado.objects.filter(carga__in=cargas_parciales).all()
    # Cada cat tiene 2 partidos + total + blancos + nulos + sobres = 6
    assert votos_carga_parcial.count() == (len(CATEGORIAS) - 1) * 6


def test_procesar_csv_informacion_valida_copia_parciales_a_totales(db, usr_unidad_basica, carga_inicial):
    ok, errores = CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_copia_parciales_a_totales.csv',
                usr_unidad_basica).procesar()
    assert ok is True
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


def test_falta_jpc_en_carga_parcial(db, usr_unidad_basica, carga_inicial):
    settings.OPCIONES_CARGAS_TOTALES_COMPLETAS = False
    ok, errores = CSVImporter(PATH_ARCHIVOS_TEST + 'falta_jpc_carga_parcial.csv', usr_unidad_basica).procesar()
    assert ok is False
    assert "Faltan las opciones: ['JpC']." in errores
    assert Carga.objects.count() == 0


def test_falta_jpc_en_carga_total(db, usr_unidad_basica, carga_inicial):
    ok, errores = CSVImporter(PATH_ARCHIVOS_TEST + 'falta_jpc_carga_total.csv', usr_unidad_basica).procesar()
    assert ok is False
    assert "Los resultados para la carga total para la categoría Intendente, Concejales y Consejeros Escolares deben estar completos. " \
           "Faltan las opciones: ['JpC']." in errores
    assert Carga.objects.count() == 0

def test_caracteres_alfabeticos_en_votos(db, usr_unidad_basica, carga_inicial):
    ok, errores = CSVImporter(PATH_ARCHIVOS_TEST + 'valores_texto_en_votos.csv', usr_unidad_basica).procesar()
    assert ok is False
    assert 'Los resultados deben ser números enteros positivos.' in errores
    assert Carga.objects.count() == 0

def test_acumula_errores(db, usr_unidad_basica, carga_inicial):
    ok, errores = CSVImporter(PATH_ARCHIVOS_TEST + 'acumula_errores.csv', usr_unidad_basica).procesar()
    assert ok is False
    print(errores)
    assert 'Los resultados deben ser números enteros positivos.' in errores
    assert "Faltan las opciones: ['JpC']." in errores
    assert Carga.objects.count() == 0


def test_procesar_csv_informacion_valida_con_listas_numericas(db, usr_unidad_basica, carga_inicial):
    fdt = Opcion.objects.get(nombre='FdT')
    fdt.codigo = '136'
    fdt.save()
    ok, errores = CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_ok_con_listas_numericas.csv', usr_unidad_basica).procesar()
    assert ok is True
    cargas_totales = Carga.objects.filter(tipo=Carga.TIPOS.total)

    # Debería haber 2 cargas total: Int (que no es prio), y presi, que es prio pero tiene
    # además opción no prioritaria.
    assert cargas_totales.count() == 2

def test_procesar_csv_carga_reemplaza_anterior(db, usr_unidad_basica, carga_inicial):
    ok, errores = CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_ok.csv', usr_unidad_basica).procesar()
    assert ok is True
    cargas_totales = Carga.objects.filter(tipo=Carga.TIPOS.total)

    assert cargas_totales.count() == 2

    ids_viejos = list(cargas_totales.values_list('id', flat=True))

    # Vuelvo a cargar.

    ok, errores = CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_ok.csv', usr_unidad_basica).procesar()
    assert ok is True
    cargas_totales = Carga.objects.filter(tipo=Carga.TIPOS.total)

    # No aumentó.
    assert cargas_totales.count() == 2
    cargas_repetidas = Carga.objects.filter(id__in=ids_viejos)
    # No quedó ninguna de las viejas.
    assert cargas_repetidas.count() == 0

def test_procesar_csv_sanitiza_ok(db, usr_unidad_basica, carga_inicial):
    fdt = Opcion.objects.get(nombre='FdT')
    fdt.codigo = '136'
    fdt.save()
    ok, errores = CSVImporter(PATH_ARCHIVOS_TEST + 'info_resultados_ok_con_sanitizar.csv', usr_unidad_basica).procesar()

    assert ok is True
    cargas_totales = Carga.objects.filter(tipo=Carga.TIPOS.total)

    # Debería haber 2 cargas total: Int (que no es prio), y presi, que es prio pero tiene
    # además opción no prioritaria.
    assert cargas_totales.count() == 2