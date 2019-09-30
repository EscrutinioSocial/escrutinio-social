import pytest

from scheduling.models import (
    mapa_prioridades_desde_setting, mapa_prioridades_para_categoria, mapa_prioridades_para_seccion,
    mapa_prioridades_para_mesa_categoria
)
from .factories import (
    PrioridadSchedulingFactory
)
from .utils_para_test import (
    verificar_registro_prioridad, asignar_prioridades_standard
)
from elecciones.tests.factories import (
    SeccionFactory, CategoriaFactory, MesaCategoriaFactory,
    CircuitoFactory, LugarVotacionFactory, MesaFactory
)
from elecciones.models import (
    Seccion, Categoria, Mesa
)

# En este archivo se incluyen los tests de calculo de prioridades teniendo en cuenta
# los objetos de esta aplicacion: Seccion, Categoria, MesaCategoria


def definir_prioridades_seccion_categoria(settings):
    asignar_prioridades_standard(settings)
    seccion_cuatro_prioridades = SeccionFactory(nombre="Cuatro prioridades")
    seccion_dos_cantidades = SeccionFactory(nombre="Dos cantidades")
    seccion_prioritaria = SeccionFactory(nombre="Prioritaria")
    seccion_standard = SeccionFactory(nombre="Standard")
    PrioridadSchedulingFactory(seccion=seccion_cuatro_prioridades, desde_proporcion=50, hasta_proporcion=100, prioridad=250)
    PrioridadSchedulingFactory(seccion=seccion_cuatro_prioridades, desde_proporcion=30, hasta_proporcion=50, prioridad=120)
    PrioridadSchedulingFactory(seccion=seccion_cuatro_prioridades, desde_proporcion=10, hasta_proporcion=30, prioridad=80)
    PrioridadSchedulingFactory(seccion=seccion_cuatro_prioridades, desde_proporcion=0,
                               hasta_proporcion=10, hasta_cantidad=12, prioridad=20)
    PrioridadSchedulingFactory(seccion=seccion_dos_cantidades, desde_proporcion=0,
                               hasta_proporcion=2, hasta_cantidad=7, prioridad=5)
    PrioridadSchedulingFactory(seccion=seccion_dos_cantidades, desde_proporcion=2,
                               hasta_proporcion=10, hasta_cantidad=20, prioridad=25)
    PrioridadSchedulingFactory(seccion=seccion_dos_cantidades, desde_proporcion=10, hasta_proporcion=100, prioridad=110)
    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=0,
                               hasta_proporcion=2, hasta_cantidad=7, prioridad=10)
    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=2, hasta_proporcion=10, prioridad=50)
    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=10, hasta_proporcion=100, prioridad=80)

    pv = CategoriaFactory(nombre="PV")
    gv = CategoriaFactory(nombre="GV")
    categoria_standard = CategoriaFactory(nombre="Standard")
    PrioridadSchedulingFactory(categoria=pv, desde_proporcion=0, hasta_proporcion=100, prioridad=5)
    PrioridadSchedulingFactory(categoria=gv, desde_proporcion=0, hasta_proporcion=100, prioridad=30)

    # tambien hay que definir una mesa en cada seccion, para lo cual tengo que definir
    # circuitos y lugares de votacion
    crear_mesa(seccion_cuatro_prioridades)
    crear_mesa(seccion_dos_cantidades)
    crear_mesa(seccion_prioritaria)
    crear_mesa(seccion_standard)


def crear_mesa(seccion):
    circuito = CircuitoFactory(seccion=seccion)
    lugar_votacion = LugarVotacionFactory(circuito=circuito)
    return MesaFactory(lugar_votacion=lugar_votacion)


def seccion_cuatro_prioridades():
    return Seccion.objects.filter(nombre="Cuatro prioridades")[0]


def seccion_dos_cantidades():
    return Seccion.objects.filter(nombre="Dos cantidades")[0]


def seccion_prioritaria():
    return Seccion.objects.filter(nombre="Prioritaria")[0]


def seccion_standard():
    return Seccion.objects.filter(nombre="Standard")[0]


def mesa_en_seccion(seccion):
    return Mesa.objects.filter(lugar_votacion__circuito__seccion=seccion)[0]


def categoria_pv():
    return Categoria.objects.filter(nombre="PV")[0]


def categoria_gv():
    return Categoria.objects.filter(nombre="GV")[0]


def categoria_standard():
    return Categoria.objects.filter(nombre="Standard")[0]


def test_prioridades_seccion(db, settings):
    definir_prioridades_seccion_categoria(settings)

    mapa = mapa_prioridades_para_seccion(seccion_cuatro_prioridades())
    regis = mapa.registros_ordenados()
    assert len(regis) == 4
    verificar_registro_prioridad(regis[0], 0, 10, 20, 12)
    verificar_registro_prioridad(regis[1], 10, 30, 80)
    verificar_registro_prioridad(regis[2], 30, 50, 120)
    verificar_registro_prioridad(regis[3], 50, 100, 250)

    mapa = mapa_prioridades_para_seccion(seccion_dos_cantidades())
    regis = mapa.registros_ordenados()
    assert len(regis) == 3
    verificar_registro_prioridad(regis[0], 0, 2, 5, 7)
    verificar_registro_prioridad(regis[1], 2, 10, 25, 20)
    verificar_registro_prioridad(regis[2], 10, 100, 110)


def test_prioridades_categoria(db, settings):
    definir_prioridades_seccion_categoria(settings)

    categoria_rara = CategoriaFactory(nombre="Marcianos")
    PrioridadSchedulingFactory(categoria=categoria_rara, desde_proporcion=0, hasta_proporcion=2, prioridad=5)
    PrioridadSchedulingFactory(categoria=categoria_rara, desde_proporcion=2,
                               hasta_proporcion=100, prioridad=30)

    mapa = mapa_prioridades_para_categoria(categoria_pv())
    regis = mapa.registros_ordenados()
    assert len(regis) == 1
    verificar_registro_prioridad(regis[0], 0, 100, 5)

    mapa = mapa_prioridades_para_categoria(categoria_rara)
    regis = mapa.registros_ordenados()
    assert len(regis) == 2
    verificar_registro_prioridad(regis[0], 0, 2, 5)
    verificar_registro_prioridad(regis[1], 2, 100, 30)

    mapa = mapa_prioridades_para_categoria(categoria_standard())
    regis = mapa.registros_ordenados()
    assert len(regis) == 0


@pytest.mark.parametrize('proporcion, orden_de_llegada, prioridad', [
    [0, 1, 200],
    [1, 2, 200],
    [2, 3, 2000],
    [4, 5, 2000],
    [9, 10, 2000],
    [10, 11, 10000],
    [80, 81, 10000],
])
def test_prioridades_mesacat_standard(db, settings, proporcion, orden_de_llegada, prioridad):
    """
    Prioridades para una MesaCategoria para la cual ni la sección ni la categoría tienen
    asignadas prioridades distintas a las standard
    """

    definir_prioridades_seccion_categoria(settings)
    
    mesa_categoria = MesaCategoriaFactory(
        categoria=categoria_standard(), mesa=mesa_en_seccion(seccion_standard()))
    prioridades = mapa_prioridades_para_mesa_categoria(mesa_categoria)

    assert(prioridades.valor_para(proporcion,orden_de_llegada)) == prioridad


@pytest.mark.parametrize('proporcion, orden_de_llegada, prioridad', [
    [0, 1, 1000],
    [1, 2, 1000],
    [2, 3, 1000],
    [6, 7, 1000],
    [7, 8, 5000],
    [9, 10, 5000],
    [10, 11, 8000],
    [80, 81, 8000],
])
def test_prioridades_mesacat_seccion_prioritaria_100(db, settings, proporcion, orden_de_llegada, prioridad):
    """
    Prioridades para una MesaCategoria de una seccion prioritaria, para una categoria sin prioridades definidas,
    en un circuito de 100 mesas.
    La maxima prioridad para la seccion rige hasta el 2% con un minimo de 7 mesas.
    """
    definir_prioridades_seccion_categoria(settings)

    mesa_categoria = MesaCategoriaFactory(
        categoria=categoria_standard(), mesa=mesa_en_seccion(seccion_prioritaria()))
    prioridades = mapa_prioridades_para_mesa_categoria(mesa_categoria)

    assert(prioridades.valor_para(proporcion, orden_de_llegada)) == prioridad


@pytest.mark.parametrize('proporcion, orden_de_llegada, prioridad', [
    [0, 1, 1000],
    [0, 2, 1000],
    [1, 15, 1000],
    [1, 20, 1000],
    [2, 21, 5000],
    [7, 80, 5000],
    [9, 100, 5000],
    [10, 101, 8000],
    [80, 801, 8000],
])
def test_prioridades_mesacat_seccion_prioritaria_1000(db, settings, proporcion, orden_de_llegada, prioridad):
    """
    Prioridades para una MesaCategoria de una seccion prioritaria, para una categoria sin prioridades definidas,
    en un circuito de 1000 mesas.
    La maxima prioridad para la seccion rige hasta el 2% con un minimo de 7 mesas.
    """
    definir_prioridades_seccion_categoria(settings)

    mesa_categoria = MesaCategoriaFactory(
        categoria=categoria_standard(), mesa=mesa_en_seccion(seccion_prioritaria()))
    prioridades = mapa_prioridades_para_mesa_categoria(mesa_categoria)

    assert(prioridades.valor_para(proporcion, orden_de_llegada)) == prioridad


@pytest.mark.parametrize('proporcion, orden_de_llegada, prioridad', [
    [0, 1, 10],
    [1, 2, 10],
    [2, 3, 100],
    [4, 5, 100],
    [9, 10, 100],
    [10, 11, 500],
    [80, 81, 500],
])
def test_prioridades_mesacat_categoria_prioritaria(db, settings, proporcion, orden_de_llegada, prioridad):
    """
    Prioridades para una MesaCategoria de una seccion standard, para una categoria prioritaria,
    en un circuito de 100 mesas.
    """
    definir_prioridades_seccion_categoria(settings)

    mesa_categoria = MesaCategoriaFactory(
        categoria=categoria_pv(), mesa=mesa_en_seccion(seccion_standard()))
    prioridades = mapa_prioridades_para_mesa_categoria(mesa_categoria)

    assert(prioridades.valor_para(proporcion, orden_de_llegada)) == prioridad


@pytest.mark.parametrize('proporcion, orden_de_llegada, prioridad', [
    [0, 1, 50],
    [1, 2, 50],
    [2, 3, 50],
    [6, 7, 50],
    [7, 8, 250],
    [9, 10, 250],
    [10, 11, 400],
    [80, 81, 400],
])
def test_prioridades_mesacat_categoria_y_seccion_prioritarias_100(db, settings, proporcion, orden_de_llegada, prioridad):
    """
    Prioridades para una MesaCategoria de una seccion prioritaria, para una categoria prioritaria,
    en un circuito de 100 mesas.
    La maxima prioridad para la seccion rige hasta el 2% con un minimo de 7 mesas.
    """
    definir_prioridades_seccion_categoria(settings)

    mesa_categoria = MesaCategoriaFactory(
        categoria=categoria_pv(), mesa=mesa_en_seccion(seccion_prioritaria()))
    prioridades = mapa_prioridades_para_mesa_categoria(mesa_categoria)

    assert(prioridades.valor_para(proporcion, orden_de_llegada)) == prioridad


@pytest.mark.parametrize('proporcion, orden_de_llegada, prioridad', [
    [0, 1, 50],
    [0, 2, 50],
    [1, 15, 50],
    [2, 25, 250],
    [7, 85, 250],
    [9, 100, 250],
    [10, 101, 400],
    [85, 855, 400],
])
def test_prioridades_mesacat_categoria_y_seccion_prioritarias_1000(db, settings, proporcion, orden_de_llegada, prioridad):
    """
    Prioridades para una MesaCategoria de una seccion prioritaria, para una categoria prioritaria,
    en un circuito de 100 mesas.
    La maxima prioridad para la seccion rige hasta el 2% con un minimo de 7 mesas.
    """
    definir_prioridades_seccion_categoria(settings)

    mesa_categoria = MesaCategoriaFactory(
        categoria=categoria_pv(), mesa=mesa_en_seccion(seccion_prioritaria()))
    prioridades = mapa_prioridades_para_mesa_categoria(mesa_categoria)

    assert(prioridades.valor_para(proporcion, orden_de_llegada)) == prioridad


@pytest.mark.parametrize('proporcion, orden_de_llegada, prioridad', [
    [0, 1, 600],
    [1, 2, 600],
    [2, 3, 600],
    [7, 8, 600],
    [9, 10, 600],
    [10, 11, 600],
    [11, 12, 600],
    [12, 13, 2400],
    [29, 30, 2400],
    [30, 31, 3600],
    [40, 41, 3600],
    [60, 61, 7500],
    [80, 81, 7500],
])
def test_prioridades_mesacat_seccion_cuatro_prioridades_100(db, settings, proporcion, orden_de_llegada, prioridad):
    """
    Prioridades para una MesaCategoria de una seccion que tiene definidas cuatro niveles de prioridad en lugar de tres, para una categoria intermedia,
    en un circuito de 100 mesas.
    La maxima prioridad para la seccion rige hasta el 2% con un minimo de 12 mesas.
    """
    definir_prioridades_seccion_categoria(settings)

    mesa_categoria = MesaCategoriaFactory(
        categoria=categoria_gv(), mesa=mesa_en_seccion(seccion_cuatro_prioridades()))
    prioridades = mapa_prioridades_para_mesa_categoria(mesa_categoria)

    assert(prioridades.valor_para(proporcion, orden_de_llegada)) == prioridad


@pytest.mark.parametrize('proporcion, orden_de_llegada, prioridad', [
    [0, 1, 600],
    [0, 7, 600],
    [1, 12, 600],
    [1, 18, 600],
    [2, 23, 600],
    [7, 84, 600],
    [9, 100, 600],
    [10, 101, 2400],
    [11, 112, 2400],
    [12, 123, 2400],
    [29, 300, 2400],
    [30, 301, 3600],
    [40, 401, 3600],
    [60, 601, 7500],
    [80, 801, 7500],
])
def test_prioridades_mesa_seccion_cuatro_prioridades_1000(db, settings, proporcion, orden_de_llegada, prioridad):
    """
    Prioridades para una MesaCategoria de una seccion que tiene definidas cuatro niveles de prioridad en lugar de tres, para una categoria intermedia,
    en un circuito de 1000 mesas.
    La maxima prioridad para la seccion rige hasta el 2% con un minimo de 12 mesas.
    """
    definir_prioridades_seccion_categoria(settings)

    mesa_categoria = MesaCategoriaFactory(
        categoria=categoria_gv(), mesa=mesa_en_seccion(seccion_cuatro_prioridades()))
    prioridades = mapa_prioridades_para_mesa_categoria(mesa_categoria)

    assert(prioridades.valor_para(proporcion, orden_de_llegada)) == prioridad


@pytest.mark.parametrize('proporcion, orden_de_llegada, prioridad', [
    [0, 1, 200],
    [1, 2, 200],
    [2, 3, 400],
    [3, 4, 400],
    [4, 5, 400],
    [5, 6, 2000],
    [9, 10, 2000],
    [10, 11, 10000],
    [11, 12, 10000],
    [19, 20, 10000],
    [20, 21, 10000],
    [40, 41, 10000],
    [60, 61, 10000],
])
def test_prioridades_mesacat_seccion_con_definicion_parcial_1(db, settings, proporcion, orden_de_llegada, prioridad):
    """
    Prioridades para una MesaCategoria de una seccion que define prioridades distintas de las standard sólo para un rango de proporciones.
    """
    definir_prioridades_seccion_categoria(settings)
    seccion_parcial = SeccionFactory(nombre="Definición parcial de prioridades no standard")
    PrioridadSchedulingFactory(seccion=seccion_parcial, desde_proporcion=2, hasta_proporcion=5, prioridad=4)

    mesa_categoria = MesaCategoriaFactory(
        categoria=categoria_standard(), mesa=crear_mesa(seccion_parcial))
    prioridades = mapa_prioridades_para_mesa_categoria(mesa_categoria)

    assert(prioridades.valor_para(proporcion, orden_de_llegada)) == prioridad


@pytest.mark.parametrize('proporcion, orden_de_llegada, prioridad', [
    [0, 1, 200],
    [1, 2, 200],
    [2, 3, 2000],
    [3, 4, 2000],
    [4, 5, 2000],
    [5, 6, 4000],
    [9, 10, 4000],
    [10, 11, 4000],
    [11, 12, 4000],
    [19, 20, 4000],
    [20, 21, 10000],
    [40, 41, 10000],
    [60, 61, 10000],
])
def test_prioridades_mesacat_seccion_con_definicion_parcial_2(db, settings, proporcion, orden_de_llegada, prioridad):
    """
    Prioridades para una MesaCategoria de una seccion que define prioridades distintas de las standard sólo para un rango de proporciones.
    Variante de test_prioridades_mesacat_seccion_con_definicion_parcial_1
    """
    definir_prioridades_seccion_categoria(settings)
    seccion_parcial = SeccionFactory(nombre="Definición parcial de prioridades no standard")
    PrioridadSchedulingFactory(seccion=seccion_parcial, desde_proporcion=5, hasta_proporcion=20, prioridad=40)

    mesa_categoria = MesaCategoriaFactory(
        categoria=categoria_standard(), mesa=crear_mesa(seccion_parcial))
    prioridades = mapa_prioridades_para_mesa_categoria(mesa_categoria)

    assert(prioridades.valor_para(proporcion, orden_de_llegada)) == prioridad
