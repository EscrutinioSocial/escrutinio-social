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
    with django_assert_num_queries(14):
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


def test_siguiente_prioriza_categoria(db, settings):
    f = FiscalFactory()
    c = CategoriaFactory(prioridad=2)
    c2 = CategoriaFactory(prioridad=1)
    m1 = MesaFactory()
    AttachmentFactory(mesa=m1)
    mc1 = MesaCategoriaFactory(
        status=MesaCategoria.STATUS.parcial_sin_consolidar,
        categoria=c,
        mesa=m1,
    )
    mc1.actualizar_coeficiente_para_orden_de_carga()
    m2 = MesaFactory()
    AttachmentFactory(mesa=m2)
    mc2 = MesaCategoriaFactory(
        categoria=c2,
        status=MesaCategoria.STATUS.parcial_sin_consolidar,
        mesa=m2,
    )
    mc2.actualizar_coeficiente_para_orden_de_carga()
    # Se recibe la mc con categoria más prioritaria.
    assert MesaCategoria.objects.siguiente() == mc2
    for i in range(settings.MIN_COINCIDENCIAS_CARGAS):
        mc2.asignar_a_fiscal()
    # Luego la de la categoría menos prioritaria.
    assert MesaCategoria.objects.siguiente() == mc1


def test_siguiente_prioriza_seccion(db, settings):
    f = FiscalFactory()
    c = CategoriaFactory()
    # Si se pone
    #     m1 = MesaFactory(circuito__seccion__prioridad_hasta_2=10000)
    # no funciona.
    # Intuyo que es porque en MesaFactory, el circuito se setea mediante un LazyAttribute,
    # y los seteos que van como argumentos de la Factory se estarían ejecutando antes de
    # que se apliquen los LazyAttribute.
    # Lo único que hice fue la prueba empírica de agregar "lugar_votacion__" antes, y ver que sí setea
    # la prioridad de la sección. No llegué a entender la documentación de factory boy en la medida necesaria.

    m1 = MesaFactory(lugar_votacion__circuito__seccion__prioridad_hasta_2=10000)
    AttachmentFactory(mesa=m1)
    mc1 = MesaCategoriaFactory(
        status=MesaCategoria.STATUS.parcial_sin_consolidar,
        categoria=c,
        mesa=m1,
    )
    mc1.actualizar_coeficiente_para_orden_de_carga()
    m2 = MesaFactory(lugar_votacion__circuito__seccion__prioridad_hasta_2=42)
    AttachmentFactory(mesa=m2)
    mc2 = MesaCategoriaFactory(
        categoria=c,
        status=MesaCategoria.STATUS.parcial_sin_consolidar,
        mesa=m2,
    )
    mc2.actualizar_coeficiente_para_orden_de_carga()
    assert mc1.percentil == 1
    assert mc1.mesa.circuito.seccion.prioridad_hasta_2 == 10000
    assert mc2.percentil == 1
    assert mc2.mesa.circuito.seccion.prioridad_hasta_2 == 42
    # Se recibe la mc de la sección más prioritaria.
    assert MesaCategoria.objects.siguiente() == mc2
    for i in range(settings.MIN_COINCIDENCIAS_CARGAS):
        mc2.asignar_a_fiscal()
    # Luego la de la sección con prioridad menos prioritaria.
    assert MesaCategoria.objects.siguiente() == mc1
