import pytest

from scheduling.models import (
    MapaPrioridades, MapaPrioridadesConDefault, MapaPrioridadesProducto,
    RegistroDePrioridad, RangosDeProporcionesSeSolapanError,
    mapa_prioridades_desde_setting
)


def test_aplica_tope():
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


@pytest.mark.parametrize('proporcion, nro_de_orden, prioridad', [
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
def test_tope(proporcion, nro_de_orden, prioridad):
    mapa = MapaPrioridades()
    mapa.agregar_registro(RegistroDePrioridad(0, 5, 20, 7))
    mapa.agregar_registro(RegistroDePrioridad(5, 25, 40))
    mapa.agregar_registro(RegistroDePrioridad(25, 100, 100))
    assert mapa.valor_para(proporcion, nro_de_orden) == prioridad


def test_mapa_desde_estructura():
    estruc = [
        {'desde': 0, 'hasta': 2, 'prioridad': 2, 'tope': 7},
        {'desde': 20, 'hasta': 100, 'prioridad': 130},
        {'desde': 2, 'hasta': 10, 'prioridad': 20},
    ]
    mapa = mapa_prioridades_desde_setting(estruc)
    regis = mapa.registros_ordenados()
    assert len(regis) == 3
    assert regis[0].desde == 0
    assert regis[0].hasta == 2
    assert regis[0].prioridad == 2
    assert regis[0].tope == 7
    assert regis[1].desde == 2
    assert regis[1].hasta == 10
    assert regis[1].prioridad == 20 
    assert regis[1].tope == None
    assert regis[2].desde == 20
    assert regis[2].hasta == 100
    assert regis[2].prioridad == 130
    assert regis[2].tope == None

