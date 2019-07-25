import pytest
from datetime import timedelta
from django.utils import timezone
from elecciones.tests.factories import (
    AttachmentFactory,
    CategoriaFactory,
    CircuitoFactory,
    FiscalFactory,
    IdentificacionFactory,
    MesaCategoriaDefaultFactory,
    MesaCategoriaFactory,
    MesaFactory,
)
from elecciones.models import MesaCategoria, Mesa
from elecciones.scheduling import (
    MapaPrioridades, MapaPrioridadesConDefault, MapaPrioridadesProducto,
    RegistroDePrioridad, RangosDeProporcionesSeSolapanError
)
from adjuntos.consolidacion import consumir_novedades_identificacion
from problemas.models import Problema, ReporteDeProblema


def test_identificacion_consolidada_calcula_orden_de_prioridad(db):
    mc1 = MesaCategoriaFactory()
    mesa = mc1.mesa
    mc2 = MesaCategoriaFactory(mesa=mesa)
    assert mc1.orden_de_carga is None
    assert mc2.orden_de_carga is None

    # emulo consolidacion
    i = IdentificacionFactory(status='identificada', mesa=mc1.mesa, fiscal=FiscalFactory())
    AttachmentFactory(status='identificada', mesa=mesa, identificacion_testigo=i)
    mc1.refresh_from_db()
    mc2.refresh_from_db()
    assert mc1.orden_de_carga is not None
    assert mc2.orden_de_carga is not None


def test_siguiente_prioriza_estado_y_luego_coeficiente(db, django_assert_num_queries):
    f = FiscalFactory()
    c = CategoriaFactory(prioridad=1)
    mc1 = MesaCategoriaFactory(
        status=MesaCategoria.STATUS.parcial_sin_consolidar,
        categoria=c,
        orden_de_carga=1.0
    )
    mc2 = MesaCategoriaFactory(
        categoria=c,
        status=MesaCategoria.STATUS.total_en_conflicto,
        orden_de_carga=99.0
    )
    mc3 = MesaCategoriaFactory(
        categoria=c,
        status=MesaCategoria.STATUS.total_en_conflicto,
        orden_de_carga=2.0
    )
    with django_assert_num_queries(1):
        assert MesaCategoria.objects.siguiente() == mc1
    mc1.take(f)
    assert MesaCategoria.objects.siguiente() == mc3
    mc3.take(f)
    assert MesaCategoria.objects.siguiente() == mc2
    mc2.take(f)
    assert MesaCategoria.objects.siguiente() is None


def test_siguiente_prioriza_categoria(db):
    f = FiscalFactory()
    c = CategoriaFactory(prioridad=2)
    c2 = CategoriaFactory(prioridad=1)
    mc1 = MesaCategoriaFactory(
        status=MesaCategoria.STATUS.parcial_sin_consolidar,
        categoria=c,
        orden_de_carga=0
    )
    mc2 = MesaCategoriaFactory(
        categoria=c2,
        status=MesaCategoria.STATUS.parcial_sin_consolidar,
        orden_de_carga=0
    )
    # se recibe la mc con categoria más baja
    assert MesaCategoria.objects.siguiente() == mc2
    mc2.take(f)
    assert MesaCategoria.objects.siguiente() == mc1
    mc1.take(f)
    assert MesaCategoria.objects.siguiente() is None


def test_siguiente_prioriza_mesa(db):
    f = FiscalFactory()
    mc1 = MesaCategoriaFactory(
        status=MesaCategoria.STATUS.parcial_sin_consolidar,
        mesa__prioridad=2,
        categoria__nombre='foo',
        orden_de_carga=0
    )
    mc2 = MesaCategoriaFactory(
        status=MesaCategoria.STATUS.parcial_sin_consolidar,
        mesa__prioridad=1,
        categoria__nombre='foo',
        orden_de_carga=0
    )

    # se recibe la mc con mesa con prioridad menor
    assert MesaCategoria.objects.siguiente() == mc2
    mc2.take(f)
    assert MesaCategoria.objects.siguiente() == mc1
    mc1.take(f)
    assert MesaCategoria.objects.siguiente() is None


@pytest.mark.parametrize('total', [10, 40])
def test_actualizar_orden_de_carga(db, total):
    c = CircuitoFactory()
    MesaFactory.create_batch(total, circuito=c)
    for i, mc in enumerate(MesaCategoria.objects.defer('orden_de_carga').all(), 1):
        mc.actualizar_orden_de_carga()
        assert mc.orden_de_carga == int(round(i/total, 2) * 100)


def test_identificadas_excluye_sin_orden(db):
    mc1 = MesaCategoriaFactory()
    mc2 = MesaCategoriaFactory(orden_de_carga=0.1)
    assert mc1.orden_de_carga is None
    assert mc1 not in MesaCategoria.objects.identificadas()
    assert mc2 in MesaCategoria.objects.identificadas()


def test_no_taken_incluye_taken_nulo(db):
    f = FiscalFactory()
    mc1 = MesaCategoriaDefaultFactory()
    mc2 = MesaCategoriaDefaultFactory()
    assert mc1.taken is None
    assert mc2.taken is None
    assert set(MesaCategoria.objects.no_taken()) == {mc1, mc2}
    mc2.take(f)
    assert mc2.taken is not None
    assert mc2.taken_by == f
    assert set(MesaCategoria.objects.no_taken()) == {mc1}


def test_no_taken_incluye_taken_vencido(db):
    now = timezone.now()
    mc1 = MesaCategoriaFactory(taken=now)
    mc2 = MesaCategoriaFactory(taken=now - timedelta(minutes=3))
    assert mc1.taken is not None
    assert mc2.taken is not None
    assert mc1 not in MesaCategoria.objects.no_taken()
    assert mc2 in MesaCategoria.objects.no_taken()


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
    mapa.agregarRegistro(RegistroDePrioridad(0, 5, 20))
    mapa.agregarRegistro(RegistroDePrioridad(5, 15, 80))
    mapa.agregarRegistro(RegistroDePrioridad(15, 100, 400))
    assert mapa.valor_para(proporcion) == prioridad


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
    mapa.agregarRegistro(RegistroDePrioridad(0, 5, 20))
    mapa.agregarRegistro(RegistroDePrioridad(15, 100, 400))
    assert mapa.valor_para(proporcion) == prioridad


def test_mapa_prioridades_con_solapamiento():
    mapa = MapaPrioridades()
    mapa.agregarRegistro(RegistroDePrioridad(10, 25, 20))
    mapa.agregarRegistro(RegistroDePrioridad(40, 80, 20))
    with pytest.raises(RangosDeProporcionesSeSolapanError) as e1:
        mapa.agregarRegistro(RegistroDePrioridad(5, 15, 50))
    assert 'De 10% a 25%' in str(e1.value)
    with pytest.raises(RangosDeProporcionesSeSolapanError) as e2:
        mapa.agregarRegistro(RegistroDePrioridad(50, 60, 50))
    assert 'De 40% a 80%' in str(e2.value)
    with pytest.raises(RangosDeProporcionesSeSolapanError) as e3:
        mapa.agregarRegistro(RegistroDePrioridad(30, 90, 50))
    assert 'De 40% a 80%' in str(e3.value)
    with pytest.raises(RangosDeProporcionesSeSolapanError) as e4:
        mapa.agregarRegistro(RegistroDePrioridad(15, 35, 50))
    assert 'De 10% a 25%' in str(e1.value)
    # los que siguen no tienen que dar error
    mapa.agregarRegistro(RegistroDePrioridad(90, 100, 20))
    mapa.agregarRegistro(RegistroDePrioridad(80, 90, 20))


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
    mapa_1.agregarRegistro(RegistroDePrioridad(0, 5, 20))
    mapa_1.agregarRegistro(RegistroDePrioridad(15, 100, 400))
    mapa_d = MapaPrioridades()
    mapa_d.agregarRegistro(RegistroDePrioridad(0, 8, 10))
    mapa_d.agregarRegistro(RegistroDePrioridad(10, 12, 15))
    mapa_d.agregarRegistro(RegistroDePrioridad(12, 30, 18))
    mapa = MapaPrioridadesConDefault(mapa_1, mapa_d)
    assert mapa.valor_para(proporcion) == prioridad


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
    mapa_1.agregarRegistro(RegistroDePrioridad(0, 5, 20))
    mapa_1.agregarRegistro(RegistroDePrioridad(15, 100, 100))
    mapa_d = MapaPrioridades()
    mapa_d.agregarRegistro(RegistroDePrioridad(0, 8, 10))
    mapa_d.agregarRegistro(RegistroDePrioridad(11, 12, 15))
    mapa_d.agregarRegistro(RegistroDePrioridad(12, 30, 18))
    factor_1 = MapaPrioridadesConDefault(mapa_1, mapa_d)
    factor_2 = MapaPrioridades()
    factor_2.agregarRegistro(RegistroDePrioridad(0, 2, 5))
    factor_2.agregarRegistro(RegistroDePrioridad(2, 10, 8))
    factor_2.agregarRegistro(RegistroDePrioridad(10, 100, 25))

    mapa = MapaPrioridadesProducto(factor_1, factor_2)
    assert mapa.valor_para(proporcion) == prioridad
