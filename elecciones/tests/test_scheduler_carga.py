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

from adjuntos.consolidacion import consumir_novedades_identificacion
from problemas.models import Problema, ReporteDeProblema


@pytest.fixture
def setup_constance(db):
    """
    Cuando se pide alguna config, Constance realiza por unica vez el setup
    de los definiciones por default de todas aquellas que no hayan sido explicitamente
    modificadas.
    Este fixture tiene el fin de forzar esa inilizacion para
    no afectar artificialmente el computo cuando se mide el numero de queries
    """
    from constance import config
    config.PRIORIDAD_STATUS


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


def test_siguiente_prioriza_estado_y_luego_coeficiente(db, setup_constance, django_assert_num_queries):

    f = FiscalFactory()
    c = CategoriaFactory(prioridad=1)
    m1 = MesaFactory()
    AttachmentFactory(mesa=m1)
    mc1 = MesaCategoriaFactory(
        status=MesaCategoria.STATUS.parcial_sin_consolidar,
        categoria=c,
        orden_de_carga=1.0,
        mesa=m1
    )
    m2 = MesaFactory()
    AttachmentFactory(mesa=m2)
    mc2 = MesaCategoriaFactory(
        categoria=c,
        status=MesaCategoria.STATUS.total_en_conflicto,
        orden_de_carga=99.0,
        mesa=m2
    )
    m3 = MesaFactory()
    AttachmentFactory(mesa=m3)
    mc3 = MesaCategoriaFactory(
        categoria=c,
        status=MesaCategoria.STATUS.total_en_conflicto,
        orden_de_carga=2.0,
        mesa=m3
    )
    with django_assert_num_queries(3):
        assert MesaCategoria.objects.siguiente() == mc1

    mc1.take(f)
    assert MesaCategoria.objects.siguiente() == mc3
    mc3.take(f)
    assert MesaCategoria.objects.siguiente() == mc2
    mc2.take(f)
    assert MesaCategoria.objects.siguiente() is None


@pytest.mark.skip('Reformular con nuevo scheduling.')
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

@pytest.mark.skip('Reformular con nuevo scheduling.')
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


@pytest.mark.skip('Reformular con nuevo scheduling.')
@pytest.mark.parametrize('total', [10, 40])
def test_actualizar_orden_de_carga(db, total):
    c = CircuitoFactory()
    MesaFactory.create_batch(total, circuito=c)
    for i, mc in enumerate(MesaCategoria.objects.defer('orden_de_carga').all(), 1):
        mc.actualizar_orden_de_carga()
        assert mc.orden_de_carga == int(round(i/total, 2) * 100)


def test_identificadas_excluye_sin_orden(db):
    m1 = MesaFactory()
    AttachmentFactory(mesa=m1)
    mc1 = MesaCategoriaFactory(mesa=m1)
    m2 = MesaFactory()
    AttachmentFactory(mesa=m2)
    mc2 = MesaCategoriaFactory(orden_de_carga=0.1, mesa=m2)
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


