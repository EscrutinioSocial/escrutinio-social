from elecciones.tests.factories import (
    AttachmentFactory,
    MesaCategoriaFactory,
    CategoriaFactory,
    IdentificacionFactory,
)
from elecciones.models import MesaCategoria


def test_identificacion_consolidada_calcula_orden_de_prioridad(db):
    mc1 = MesaCategoriaFactory()
    mesa = mc1.mesa
    mc2 = MesaCategoriaFactory(mesa=mesa)
    assert mc1.orden_de_carga is None
    assert mc2.orden_de_carga is None

    # emulo consolidacion
    i = IdentificacionFactory(status='identificada', mesa=mc1.mesa)
    AttachmentFactory(status='identificada', mesa=mesa, identificacion_testigo=i)
    mc1.refresh_from_db()
    mc2.refresh_from_db()
    assert mc1.orden_de_carga is not None
    assert mc2.orden_de_carga is not None


def test_siguiente_prioriza_estado_y_luego_coeficiente(db, django_assert_num_queries):
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
    mc1.take()
    assert MesaCategoria.objects.siguiente() == mc3
    mc3.take()
    assert MesaCategoria.objects.siguiente() == mc2
    mc2.take()
    assert MesaCategoria.objects.siguiente() is None



