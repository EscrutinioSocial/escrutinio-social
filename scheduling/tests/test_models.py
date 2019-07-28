import pytest

from scheduling.models import (
    mapa_prioridades_desde_setting, mapa_prioridades_para_categoria, mapa_prioridades_para_seccion,
    mapa_prioridades_para_mesa_categoria
)
from .factories import (
    PrioridadSchedulingFactory
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


def verificar_registro_prioridad(regi, desde_proporcion, hasta_proporcion, prioridad, hasta_cantidad=None):
    assert regi.desde_proporcion == desde_proporcion
    assert regi.hasta_proporcion == hasta_proporcion
    assert regi.prioridad == prioridad
    assert regi.hasta_cantidad == hasta_cantidad


def definir_prioridades_seccion_categoria(settings):
    settings.PRIORIDADES_STANDARD_SECCION = [
        {'desde_proporcion': 0, 'hasta_proporcion': 2, 'prioridad': 2},
        {'desde_proporcion': 2, 'hasta_proporcion': 10, 'prioridad': 20},
        {'desde_proporcion': 10, 'hasta_proporcion': 100, 'prioridad': 100},
    ]
    settings.PRIORIDADES_STANDARD_CATEGORIA = [
        {'desde_proporcion': 0, 'hasta_proporcion': 100, 'prioridad': 100},
    ]

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
def test_prioridades_mesa_categoria_standard(db, settings, proporcion, orden_de_llegada, prioridad):
    """
    Prioridades para una MesaCategoria para la cual ni la sección ni la categoría tienen 
    asignadas prioridades distintas a las standard
    """

    definir_prioridades_seccion_categoria(settings)
    
    mesa_categoria = MesaCategoriaFactory(
        categoria=categoria_standard(), mesa=mesa_en_seccion(seccion_standard()))
    prioridades = mapa_prioridades_para_mesa_categoria(mesa_categoria)

    assert(prioridades.valor_para(proporcion,orden_de_llegada)) == prioridad


    # PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=0,
    #                            hasta_proporcion=2, hasta_cantidad=7, prioridad=10)
    # PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=2, hasta_proporcion=10, prioridad=50)
    # PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=10, hasta_proporcion=100, prioridad=80)
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
def test_prioridades_mesa_categoria_seccion_prioritaria_100(db, settings, proporcion, orden_de_llegada, prioridad):
    """
    Prioridades para una MesaCategoria de una seccion prioritaria, para una categoria sin prioridades definidas,
    en un circuito de 100 mesas.
    La maxima prioridad para la seccion rige hasta el 2% con un minimo de 7 mesas.
    """

    definir_prioridades_seccion_categoria(settings)
    
    mesa_categoria = MesaCategoriaFactory(
        categoria=categoria_standard(), mesa=mesa_en_seccion(seccion_prioritaria()))
    prioridades = mapa_prioridades_para_mesa_categoria(mesa_categoria)

    assert(prioridades.valor_para(proporcion,orden_de_llegada)) == prioridad
