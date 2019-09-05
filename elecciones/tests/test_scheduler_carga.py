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

from adjuntos.consolidacion import consumir_novedades_identificacion, liberar_mesacategorias_y_attachments
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
    assert mc1.coeficiente_para_orden_de_carga is None
    assert mc2.coeficiente_para_orden_de_carga is None

    # Emulo consolidación.
    i = IdentificacionFactory(status='identificada', mesa=mc1.mesa, fiscal=FiscalFactory())
    AttachmentFactory(status='identificada', mesa=mesa, identificacion_testigo=i)
    mc1.refresh_from_db()
    mc2.refresh_from_db()
    assert mc1.coeficiente_para_orden_de_carga is not None
    assert mc2.coeficiente_para_orden_de_carga is not None


def test_siguiente_prioriza_estado_y_luego_coeficiente(db, settings, setup_constance, django_assert_num_queries):

    f = FiscalFactory()
    c = CategoriaFactory(prioridad=1)
    m1 = MesaFactory()
    AttachmentFactory(mesa=m1)
    mc1 = MesaCategoriaFactory(
        status=MesaCategoria.STATUS.parcial_sin_consolidar,
        categoria=c,
        coeficiente_para_orden_de_carga=1.0,
        mesa=m1
    )
    m2 = MesaFactory()
    AttachmentFactory(mesa=m2)
    mc2 = MesaCategoriaFactory(
        categoria=c,
        status=MesaCategoria.STATUS.total_en_conflicto,
        coeficiente_para_orden_de_carga=99.0,
        mesa=m2
    )
    m3 = MesaFactory()
    AttachmentFactory(mesa=m3)
    mc3 = MesaCategoriaFactory(
        categoria=c,
        status=MesaCategoria.STATUS.total_en_conflicto,
        coeficiente_para_orden_de_carga=2.0,
        mesa=m3
    )
    with django_assert_num_queries(11):
        assert MesaCategoria.objects.siguiente() == mc1

    for i in range(settings.MIN_COINCIDENCIAS_CARGAS):
        mc1.asignar_a_fiscal()
    assert MesaCategoria.objects.siguiente() == mc3
    for i in range(settings.MIN_COINCIDENCIAS_CARGAS):
        mc3.asignar_a_fiscal()
    assert MesaCategoria.objects.siguiente() == mc2
    for i in range(settings.MIN_COINCIDENCIAS_CARGAS):
        mc2.asignar_a_fiscal()

    # A igualdad de asignaciones, se vuelven a repetir.
    assert MesaCategoria.objects.siguiente() == mc1
    for i in range(settings.MIN_COINCIDENCIAS_CARGAS):
        mc1.asignar_a_fiscal()
    assert MesaCategoria.objects.siguiente() == mc3
    for i in range(settings.MIN_COINCIDENCIAS_CARGAS):
        mc3.asignar_a_fiscal()
    assert MesaCategoria.objects.siguiente() == mc2


def test_identificadas_excluye_sin_orden(db):
    m1 = MesaFactory()
    AttachmentFactory(mesa=m1)
    mc1 = MesaCategoriaFactory(mesa=m1)
    m2 = MesaFactory()
    AttachmentFactory(mesa=m2)
    mc2 = MesaCategoriaFactory(coeficiente_para_orden_de_carga=0.1, mesa=m2)
    assert mc1.coeficiente_para_orden_de_carga is None
    assert mc1 not in MesaCategoria.objects.identificadas()
    assert mc2 in MesaCategoria.objects.identificadas()

def test_liberacion_vuelve_al_ruedo(db, settings):
    """
    Este test verifica que la acción del consolidador libera mesas que nunca recibieron resultados.
    """

    f = FiscalFactory()
    c = CategoriaFactory(prioridad=1)
    m1 = MesaFactory()
    AttachmentFactory(mesa=m1)
    mc1 = MesaCategoriaFactory(
        status=MesaCategoria.STATUS.parcial_sin_consolidar,
        categoria=c,
        coeficiente_para_orden_de_carga=1.0,
        mesa=m1
    )
    m3 = MesaFactory()
    AttachmentFactory(mesa=m3)
    mc3 = MesaCategoriaFactory(
        categoria=c,
        status=MesaCategoria.STATUS.total_en_conflicto,
        coeficiente_para_orden_de_carga=2.0,
        mesa=m3
    )
    assert MesaCategoria.objects.siguiente() == mc1

    for i in range(settings.MIN_COINCIDENCIAS_CARGAS):
        mc1.asignar_a_fiscal()
    cant_asignaciones = mc1.cant_fiscales_asignados

    # Es como si de las varias asignaciones de la mc la última sea para el fiscal f
    f.asignar_mesa_categoria(mc1)

    # Como mc1 está muy asignada, ahora me propone mc3.
    assert MesaCategoria.objects.siguiente() == mc3
    settings.TIMEOUT_TAREAS = 0
    liberar_mesacategorias_y_attachments()

    # mc1 volvió al ruedo.
    assert MesaCategoria.objects.siguiente() == mc1
    mc1.refresh_from_db()
    assert mc1.cant_fiscales_asignados == cant_asignaciones - 1
