import pytest

from scheduling.models import (
    MapaPrioridades, MapaPrioridadesConDefault, MapaPrioridadesProducto,
    RegistroDePrioridad, RangosDeProporcionesSeSolapanError,
    mapa_prioridades_desde_setting, mapa_prioridades_para_categoria, mapa_prioridades_para_seccion
)
from .factories import (
    PrioridadSchedulingFactory
)
from elecciones.tests.factories import (
    SeccionFactory, CategoriaFactory
)


def test_aplica_hasta_cantidad():
    regi = RegistroDePrioridad(0, 5, 20, 7)
    assert regi.aplica(2,2)
    assert regi.aplica(12,4)
    assert not regi.aplica(12,8)


@pytest.mark.parametrize('proporcion, prioridad', [
    [0, 20],
    [2, 20],
    [4.5, 20],
    [5, 80],
    [12, 80],
    [14.99, 80],
    [15, 400],
    [15.01, 400],
    [80.5, 400],
    [99.5, 400],
    [100, 400]
])
def test_mapa_prioridades_simple(proporcion, prioridad):
    mapa = MapaPrioridades()
    mapa.agregar_registro(RegistroDePrioridad(0, 5, 20))
    mapa.agregar_registro(RegistroDePrioridad(5, 15, 80))
    mapa.agregar_registro(RegistroDePrioridad(15, 100, 400))
    assert mapa.valor_para(proporcion, 1) == prioridad


@pytest.mark.parametrize('proporcion, prioridad', [
    [0, 20],
    [2, 20],
    [4.5, 20],
    [5, None],
    [12, None],
    [14.99, None],
    [15, 400],
    [15.01, 400],
    [80.5, 400],
    [99.5, 400],
    [100, 400]
])
def test_mapa_prioridades_incompleto(proporcion, prioridad):
    mapa = MapaPrioridades()
    mapa.agregar_registro(RegistroDePrioridad(0, 5, 20))
    mapa.agregar_registro(RegistroDePrioridad(15, 100, 400))
    assert mapa.valor_para(proporcion, 1) == prioridad


def test_mapa_prioridades_con_solapamiento():
    mapa = MapaPrioridades()
    mapa.agregar_registro(RegistroDePrioridad(10, 25, 20))
    mapa.agregar_registro(RegistroDePrioridad(40, 80, 20))
    with pytest.raises(RangosDeProporcionesSeSolapanError) as e1:
        mapa.agregar_registro(RegistroDePrioridad(5, 15, 50))
    assert 'De 10% a 25%' in str(e1.value)
    with pytest.raises(RangosDeProporcionesSeSolapanError) as e2:
        mapa.agregar_registro(RegistroDePrioridad(50, 60, 50))
    assert 'De 40% a 80%' in str(e2.value)
    with pytest.raises(RangosDeProporcionesSeSolapanError) as e3:
        mapa.agregar_registro(RegistroDePrioridad(30, 90, 50))
    assert 'De 40% a 80%' in str(e3.value)
    with pytest.raises(RangosDeProporcionesSeSolapanError) as e4:
        mapa.agregar_registro(RegistroDePrioridad(15, 35, 50))
    assert 'De 10% a 25%' in str(e1.value)
    # los que siguen no tienen que dar error
    mapa.agregar_registro(RegistroDePrioridad(90, 100, 20))
    mapa.agregar_registro(RegistroDePrioridad(80, 90, 20))


@pytest.mark.parametrize('proporcion, prioridad', [
    [0, 20],
    [2, 20],
    [4.5, 20],
    [5, 10],
    [7, 10],
    [8, None],
    [11, 15],
    [12, 18],
    [14.99, 18],
    [15, 400],
    [15.01, 400],
    [80.5, 400],
    [99.5, 400],
    [100, 400]
])
def test_mapa_prioridades_con_default(proporcion, prioridad):
    mapa_1 = MapaPrioridades()
    mapa_1.agregar_registro(RegistroDePrioridad(0, 5, 20))
    mapa_1.agregar_registro(RegistroDePrioridad(15, 100, 400))
    mapa_d = MapaPrioridades()
    mapa_d.agregar_registro(RegistroDePrioridad(0, 8, 10))
    mapa_d.agregar_registro(RegistroDePrioridad(10, 12, 15))
    mapa_d.agregar_registro(RegistroDePrioridad(12, 30, 18))
    mapa = MapaPrioridadesConDefault(mapa_1, mapa_d)
    assert mapa.valor_para(proporcion, 1) == prioridad


@pytest.mark.parametrize('proporcion, prioridad', [
    [0, 100],
    [1, 100],
    [2, 160],
    [4.5, 160],
    [5, 80],
    [7, 80],
    [8, None],
    [11, 375],
    [12, 450],
    [14.99, 450],
    [15, 2500],
    [15.01, 2500],
    [80, 2500],
])
def test_mapa_prioridades_producto(proporcion, prioridad):
    mapa_1 = MapaPrioridades()
    mapa_1.agregar_registro(RegistroDePrioridad(0, 5, 20))
    mapa_1.agregar_registro(RegistroDePrioridad(15, 100, 100))
    mapa_d = MapaPrioridades()
    mapa_d.agregar_registro(RegistroDePrioridad(0, 8, 10))
    mapa_d.agregar_registro(RegistroDePrioridad(11, 12, 15))
    mapa_d.agregar_registro(RegistroDePrioridad(12, 30, 18))
    factor_1 = MapaPrioridadesConDefault(mapa_1, mapa_d)
    factor_2 = MapaPrioridades()
    factor_2.agregar_registro(RegistroDePrioridad(0, 2, 5))
    factor_2.agregar_registro(RegistroDePrioridad(2, 10, 8))
    factor_2.agregar_registro(RegistroDePrioridad(10, 100, 25))

    mapa = MapaPrioridadesProducto(factor_1, factor_2)
    assert mapa.valor_para(proporcion, 1) == prioridad


@pytest.mark.parametrize('proporcion, orden_de_llegada, prioridad', [
    [0, 1, 20],
    [4, 3, 20],
    [10, 6, 20],
    [12, 7, 20],
    [14, 8, 40],
    [24, 13, 40],
    [26, 14, 100],
    [80, 41, 100],
    [5, 2, 20],
    [20, 5, 20],
    [25, 6, 20],
    [30, 7, 20],
    [35, 8, 100],
    [70, 15, 100],
    [95, 20, 100],
])
def test_hasta_cantidad(proporcion, orden_de_llegada, prioridad):
    mapa = MapaPrioridades()
    mapa.agregar_registro(RegistroDePrioridad(0, 5, 20, 7))
    mapa.agregar_registro(RegistroDePrioridad(5, 25, 40))
    mapa.agregar_registro(RegistroDePrioridad(25, 100, 100))
    assert mapa.valor_para(proporcion, orden_de_llegada) == prioridad

def verificar_registro_prioridad(regi, desde_proporcion, hasta_proporcion, prioridad, hasta_cantidad=None):
    assert regi.desde_proporcion == desde_proporcion
    assert regi.hasta_proporcion == hasta_proporcion
    assert regi.prioridad == prioridad
    assert regi.hasta_cantidad == hasta_cantidad

def test_mapa_desde_estructura():
    estruc = [
        {'desde_proporcion': 0, 'hasta_proporcion': 2, 'prioridad': 2, 'hasta_cantidad': 7},
        {'desde_proporcion': 20, 'hasta_proporcion': 100, 'prioridad': 130},
        {'desde_proporcion': 2, 'hasta_proporcion': 10, 'prioridad': 20},
    ]
    mapa = mapa_prioridades_desde_setting(estruc)
    regis = mapa.registros_ordenados()
    assert len(regis) == 3
    verificar_registro_prioridad(regis[0], 0, 2, 2, 7)
    verificar_registro_prioridad(regis[1], 2, 10, 20)
    verificar_registro_prioridad(regis[2], 20, 100, 130)


def test_prioridades_seccion(db):
    seccion_1 = SeccionFactory()
    seccion_2 = SeccionFactory()
    PrioridadSchedulingFactory(seccion=seccion_1, desde_proporcion=50, hasta_proporcion=100, prioridad=250)
    PrioridadSchedulingFactory(seccion=seccion_1, desde_proporcion=30, hasta_proporcion=50, prioridad=120)
    PrioridadSchedulingFactory(seccion=seccion_1, desde_proporcion=10, hasta_proporcion=30, prioridad=80)
    PrioridadSchedulingFactory(seccion=seccion_1, desde_proporcion=0, hasta_proporcion=10, hasta_cantidad=12, prioridad=20)
    PrioridadSchedulingFactory(seccion=seccion_2, desde_proporcion=0, hasta_proporcion=2, hasta_cantidad=7, prioridad=5)
    PrioridadSchedulingFactory(seccion=seccion_2, desde_proporcion=2, hasta_proporcion=10, hasta_cantidad=20, prioridad=25)
    PrioridadSchedulingFactory(seccion=seccion_2, desde_proporcion=10, hasta_proporcion=100, prioridad=110)    

    mapa = mapa_prioridades_para_seccion(seccion_1)
    regis = mapa.registros_ordenados()
    assert len(regis) == 4
    verificar_registro_prioridad(regis[0], 0, 10, 20, 12)
    verificar_registro_prioridad(regis[1], 10, 30, 80)
    verificar_registro_prioridad(regis[2], 30, 50, 120)
    verificar_registro_prioridad(regis[3], 50, 100, 250)

    mapa = mapa_prioridades_para_seccion(seccion_2)
    regis = mapa.registros_ordenados()
    assert len(regis) == 3
    verificar_registro_prioridad(regis[0], 0, 2, 5, 7)
    verificar_registro_prioridad(regis[1], 2, 10, 25, 20)
    verificar_registro_prioridad(regis[2], 10, 100, 110)


def test_prioridades_categoria(db):
    categoria_1 = CategoriaFactory()
    categoria_2 = CategoriaFactory()
    categoria_3 = CategoriaFactory()
    PrioridadSchedulingFactory(categoria=categoria_1, desde_proporcion=0, hasta_proporcion=100, prioridad=20)
    PrioridadSchedulingFactory(categoria=categoria_2, desde_proporcion=0, hasta_proporcion=2, prioridad=5)
    PrioridadSchedulingFactory(categoria=categoria_2, desde_proporcion=2, hasta_proporcion=100, prioridad=30)

    mapa = mapa_prioridades_para_categoria(categoria_1)
    regis = mapa.registros_ordenados()
    assert len(regis) == 1
    verificar_registro_prioridad(regis[0], 0, 100, 20)

    mapa = mapa_prioridades_para_categoria(categoria_2)
    regis = mapa.registros_ordenados()
    assert len(regis) == 2
    verificar_registro_prioridad(regis[0], 0, 2, 5)
    verificar_registro_prioridad(regis[1], 2, 100, 30)

    mapa = mapa_prioridades_para_categoria(categoria_3)
    regis = mapa.registros_ordenados()
    assert len(regis) == 0
