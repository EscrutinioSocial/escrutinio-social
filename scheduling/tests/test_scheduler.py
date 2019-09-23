from elecciones.models import (
    MesaCategoria, Carga
)
from elecciones.tests.factories import (
    AttachmentFactory,
    CargaFactory,
    CategoriaFactory,
    CategoriaOpcionFactory,
    IdentificacionFactory,
    MesaCategoriaFactory,
    MesaFactory,
    OpcionFactory,
    VotoMesaReportadoFactory,
    FiscalFactory
)

from elecciones.tests.conftest import fiscal_client, setup_groups, fiscal_client_from_fiscal    # noqa
from constance.test import override_config
from scheduling.models import ColaCargasPendientes
from adjuntos.models import Identificacion, Attachment
from adjuntos.consolidacion import consumir_novedades_identificacion, consumir_novedades_carga
from scheduling.scheduler import scheduler


def test_scheduler(db, settings):
    """
    Ejecutar dos veces el scheduler sin nuevas cosas no cambia el estado.
    """

    # Creamos 5 attachments sin identificar
    attachments = AttachmentFactory.create_batch(5, status=Attachment.STATUS.sin_identificar)

    c1 = CategoriaFactory()
    c2 = CategoriaFactory()
    m1 = MesaFactory(categorias=[c1])
    IdentificacionFactory(
        mesa=m1,
        status=Identificacion.STATUS.identificada,
        source=Identificacion.SOURCES.web,
    )
    m2 = MesaFactory(categorias=[c1, c2])

    IdentificacionFactory(
        mesa=m2,
        status=Identificacion.STATUS.identificada,
        source=Identificacion.SOURCES.csv,
    )

    # Los cinco del principio y los dos de la identificación.
    assert Attachment.objects.count() == 7
    assert MesaCategoria.objects.count() == 3

    # Empezamos con la cola vacía.
    assert ColaCargasPendientes.largo_cola() == 0

    # Ejecutar el scheduler antes de consolidar sólo encola identificaciones:
    # 2 por cada una de las fotos no identificadas y 1 para las creadas con
    # IdentificationFactory.

    scheduler()
    assert ColaCargasPendientes.largo_cola() == 5 * settings.MIN_COINCIDENCIAS_IDENTIFICACION + 2 * (settings.MIN_COINCIDENCIAS_IDENTIFICACION - 1)

    # Al consumir las novedades de identificación, se consolidan las
    # categorías de la segunda mesa, así que agregamos 4 tareas.
    consumir_novedades_identificacion()
    scheduler()
    assert ColaCargasPendientes.largo_cola() == 16
    cola_primera = ColaCargasPendientes.objects.all()

    consumir_novedades_identificacion()
    scheduler()
    # Al volver ejecutar el scheduler sin que haya novedades se mantiene la
    # misma cantidad de tareas.
    assert ColaCargasPendientes.largo_cola() == 16
    cola_segunda = ColaCargasPendientes.objects.all()

    # Testeamos la igualdad de las colas con la inclusión mutua.
    for i in cola_primera:
        assert i in cola_segunda
    for i in cola_segunda:
        assert i in cola_primera


def consumir(es_attachment=True):
    """
    Consumo una tarea y espero que sea attachment (o no).
    """
    (mc, attachment) = ColaCargasPendientes.siguiente_tarea(fiscal=None)
    if es_attachment:
        assert mc is None and attachment is not None
    else:
        assert attachment is None and mc is not None


def test_scheduler_orden_estandar(db, settings):
    # Creamos 5 attachments sin identificar
    attachments = AttachmentFactory.create_batch(5, status=Attachment.STATUS.sin_identificar)

    c1 = CategoriaFactory()
    c2 = CategoriaFactory()
    m1 = MesaFactory(categorias=[c1])
    IdentificacionFactory(
        mesa=m1,
        status='identificada',
        source=Identificacion.SOURCES.csv,
    )
    m2 = MesaFactory(categorias=[c1, c2])
    assert MesaCategoria.objects.count() == 3
    IdentificacionFactory(
        mesa=m2,
        status='identificada',
        source=Identificacion.SOURCES.csv,
    )
    # Ambas consolidadas vía csv.

    consumir_novedades_identificacion()
    with override_config(COEFICIENTE_IDENTIFICACION_VS_CARGA=10):
        scheduler()
    assert ColaCargasPendientes.largo_cola() == 16

    # Las primeras seis tareas son de carga de votos.
    for i in range(6):
        consumir(False)

    assert ColaCargasPendientes.largo_cola() == 10

    # las siguientes diez son identificaciones.
    for i in range(10):
        consumir()

    assert ColaCargasPendientes.largo_cola() == 0

    # Ya no queda nada en la cola.
    (mc, attachment) = ColaCargasPendientes.siguiente_tarea(fiscal=None)
    assert mc is None and attachment is None


def test_scheduler_orden_distinto(db, settings):
    # Creamos 5 attachments sin identificar
    attachments = AttachmentFactory.create_batch(5, status=Attachment.STATUS.sin_identificar)

    c1 = CategoriaFactory()
    c2 = CategoriaFactory()
    m1 = MesaFactory(categorias=[c1])
    IdentificacionFactory(
        mesa=m1,
        status='identificada',
        source=Identificacion.SOURCES.csv,
    )
    m2 = MesaFactory(categorias=[c1, c2])
    assert MesaCategoria.objects.count() == 3
    IdentificacionFactory(
        mesa=m2,
        status='identificada',
        source=Identificacion.SOURCES.csv,
    )
    # Ambas consolidadas vía csv.

    consumir_novedades_identificacion()
    # Si hay más fotos que attachments primero se ponen las fotos,
    # hasta que haya la misma cantidad de cargas pendients.
    with override_config(COEFICIENTE_IDENTIFICACION_VS_CARGA=1):
        scheduler()
    assert ColaCargasPendientes.largo_cola() == 16

    # items = ColaCargasPendientes.objects.all().order_by('orden')
    # for i in range(16):
    #     it = items[i]
    #     print(f'{i}: ({it.orden},{it.attachment},{it.mesa_categoria})')

    # Las primeras seis tareas son de identificaciones.
    for i in range(6):
        consumir()

    assert ColaCargasPendientes.largo_cola() == 10

    # Luego vienen dos cargas...
    for i in range(2):
        consumir(False)

    assert ColaCargasPendientes.largo_cola() == 8

    # luego dos identificaciones y dos cargas, dos veces:
    for j in range(2):
        for i in range(2):
            consumir()

        for i in range(2):
            consumir(False)

    # Ya no queda nada en la cola.
    assert ColaCargasPendientes.largo_cola() == 0
    (mc, attachment) = ColaCargasPendientes.siguiente_tarea(fiscal=None)
    assert mc is None and attachment is None
