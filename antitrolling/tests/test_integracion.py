import pytest
from elecciones.models import MesaCategoria, Carga
from adjuntos.models import Attachment, Identificacion
from adjuntos.consolidacion import (
    consolidar_identificaciones, consolidar_cargas,
    consumir_novedades_carga, consumir_novedades_identificacion
)
from antitrolling.models import EventoScoringTroll
from elecciones.tests.factories import (
    MesaFactory, AttachmentFactory,
    CategoriaFactory, CategoriaOpcionFactory)

from .utils_para_test import (
    nuevo_fiscal, identificar, reportar_problema_attachment,
    nueva_categoria, nueva_carga, reportar_problema_mesa_categoria
)


def test_asociacion_attachment_con_antitrolling(db, settings):
    """
    Se simula que se asocia un Attachment a una mesa, usando la función de consolidación.
    Se comprueba que el efecto sobre el scoring de troll de los fiscales que hicieron identificaciones es el correcto.
    """

    settings.SCORING_TROLL_IDENTIFICACION_DISTINTA_A_CONFIRMADA = 180
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2
    settings.MIN_COINCIDENCIAS_IDENTIFICACION_PROBLEMA = 2

    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    fiscal_3 = nuevo_fiscal()
    fiscal_4 = nuevo_fiscal()
    mesa_1 = MesaFactory()
    mesa_2 = MesaFactory()
    attach = AttachmentFactory()

    # empezamos con dos identificaciones a mesas distintas
    identificar(attach, mesa_1, fiscal_1)
    identificar(attach, mesa_2, fiscal_3)
    # hasta aca no debería asociarse la mesa, ergo no se afecta el scoring troll de ningun fiscal
    consolidar_identificaciones(attach)
    for fiscal in [fiscal_1, fiscal_2, fiscal_3, fiscal_4]:
        assert fiscal.scoring_troll() == 0

    # se agregan dos nuevas identificaciones: el fiscal 2 identifica la misma mesa que el 1, el fiscal 4 reporta un problema
    identificar(attach, mesa_1, fiscal_2)
    reportar_problema_attachment(attach, fiscal_4)
    # ahora si deberia asociarse la mesa, y como consecuencia,
    # aumentar el scoring troll para los fiscales 3 y 4 que identificaron distinto a lo que se decidio
    consolidar_identificaciones(attach)
    assert fiscal_1.scoring_troll() == 0
    assert fiscal_2.scoring_troll() == 0
    assert fiscal_3.scoring_troll() == 180
    assert fiscal_4.scoring_troll() == 180


def test_confirmacion_carga_total_mesa_categoria_con_antitrolling(db, settings):
    """
    Se simula que se confirma la carga total de una MesaCategoria, usando la función de consolidación.
    Se comprueba que el efecto sobre el scoring de troll de los fiscales que hicieron cargas es el correcto.
    Nota: la funcion auxiliar nueva_carga agrega una carga de tipo total.
    """

    settings.MIN_COINCIDENCIAS_CARGAS = 2
    settings.MIN_COINCIDENCIAS_CARGAS_PROBLEMA = 2
    settings.SCORING_TROLL_PROBLEMA_MESA_CATEGORIA_CON_CARGA_CONFIRMADA = 150

    # escenario
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    fiscal_3 = nuevo_fiscal()
    fiscal_4 = nuevo_fiscal()
    fiscal_5 = nuevo_fiscal()
    categoria = nueva_categoria(["o1", "o2", "o3"])
    mesa = MesaFactory(categorias=[categoria])
    mesa_categoria = MesaCategoria.objects.filter(mesa=mesa).first()

    # entran cuatro cargas: tres con resultados diferentes, una que marca un problema
    carga_1 = nueva_carga(mesa_categoria, fiscal_1, [32, 20, 10])
    carga_2 = nueva_carga(mesa_categoria, fiscal_2, [30, 20, 10])
    carga_3 = nueva_carga(mesa_categoria, fiscal_3, [5, 40, 15])
    carga_4 = reportar_problema_mesa_categoria(mesa_categoria, fiscal_4)
    # la consolidacion no deberia afectar el scoring de ningun fiscal, porque la mesa_categoria no queda consolidada
    consolidar_cargas(mesa_categoria)
    for fiscal in [fiscal_1, fiscal_2, fiscal_3, fiscal_4, fiscal_5]:
        assert fiscal.scoring_troll() == 0

    # entra una quinta carga, coincidente con la segunda
    carga_5 = nueva_carga(mesa_categoria, fiscal_5, [30, 20, 10])
    # ahora la mesa_categoria queda consolidada, y por lo tanto, deberia afectarse el scoring de los fiscales
    # cuya carga no coincide con la aceptada
    consolidar_cargas(mesa_categoria)
    assert fiscal_1.scoring_troll() == 2
    assert fiscal_2.scoring_troll() == 0
    assert fiscal_3.scoring_troll() == 50
    assert fiscal_4.scoring_troll() == 150
    assert fiscal_5.scoring_troll() == 0


def test_carga_confirmada_troll_vuelve_a_sin_consolidar(db, settings):
    """
    Se verifica que luego de que un fiscal que habia hecho una carga aceptada es detectado como troll,
    y que posteriormente se ejecuta una consolidacion de cargas,
    el estado de la MesaCategoria donde participo el troll vuelve a "sin consolidar"
    """

    settings.SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL = 50
    settings.MIN_COINCIDENCIAS_CARGAS = 2

    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    fiscal_3 = nuevo_fiscal()
    fiscal_4 = nuevo_fiscal()
    fiscal_5 = nuevo_fiscal()
    categoria_1 = nueva_categoria(["o1", "o2", "o3"])
    categoria_2 = nueva_categoria(["p1", "p2", "p3", "p4"])

    mesa_1 = MesaFactory(categorias=[categoria_1, categoria_2])
    mesa_2 = MesaFactory(categorias=[categoria_1, categoria_2])

    mesa_categoria_1_1 = MesaCategoria.objects.filter(mesa=mesa_1, categoria=categoria_1).first()
    carga_1_1_1 = nueva_carga(mesa_categoria_1_1, fiscal_1, [20, 25, 15])  # 20 de diferencia
    carga_1_1_2 = nueva_carga(mesa_categoria_1_1, fiscal_2, [30, 20, 10])
    carga_1_1_3 = nueva_carga(mesa_categoria_1_1, fiscal_3, [30, 20, 10])
    mesa_categoria_1_2 = MesaCategoria.objects.filter(mesa=mesa_1, categoria=categoria_2).first()
    carga_1_2_1 = nueva_carga(mesa_categoria_1_2, fiscal_1, [30, 15, 10, 5])
    carga_1_2_3 = nueva_carga(mesa_categoria_1_2, fiscal_3, [30, 15, 10, 5])
    mesa_categoria_2_1 = MesaCategoria.objects.filter(mesa=mesa_2, categoria=categoria_1).first()
    carga_2_1_2 = nueva_carga(mesa_categoria_2_1, fiscal_2, [60, 30, 15])
    carga_2_1_4 = nueva_carga(mesa_categoria_2_1, fiscal_4, [60, 30, 15])
    mesa_categoria_2_2 = MesaCategoria.objects.filter(mesa=mesa_2, categoria=categoria_2).first()
    carga_2_2_1 = nueva_carga(mesa_categoria_2_2, fiscal_1, [60, 20, 18, 7])  # 40 de diferencia
    carga_2_2_4 = nueva_carga(mesa_categoria_2_2, fiscal_4, [40, 30, 25, 10])

    def refrescar_data():
        for mesa_categoria in [mesa_categoria_1_1, mesa_categoria_1_2, mesa_categoria_2_1, mesa_categoria_2_2]:
            mesa_categoria.refresh_from_db()
        for fiscal in [fiscal_1, fiscal_2, fiscal_3, fiscal_4, fiscal_5]:
            fiscal.refresh_from_db()

    assert Carga.objects.filter(procesada=False).count() == 9
    assert Carga.objects.filter(invalidada=True).count() == 0
    assert not fiscal_1.troll

    # hasta aca: (1,1), (1,2) y (2,1) consolidadas, (2,2) en conflicto, fiscal_1 tiene 20 de scoring troll
    consumir_novedades_carga()
    refrescar_data()
    for mesa_categoria in [mesa_categoria_1_1, mesa_categoria_1_2, mesa_categoria_2_1]:
        assert mesa_categoria.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mesa_categoria_2_2.status == MesaCategoria.STATUS.total_en_conflicto
    assert fiscal_1.scoring_troll() == 20
    assert not fiscal_1.troll
    assert Carga.objects.filter(procesada=False).count() == 0
    assert Carga.objects.filter(invalidada=True).count() == 0

    # ahora hago una carga que confirma la MC (2,2). Esto tiene que desencadenar que
    # - el fiscal 1 se detecta como troll
    # - sus cargas pasan a invalidadas y pendientes de proceso
    carga_2_2_5 = nueva_carga(mesa_categoria_2_2, fiscal_5, [40, 30, 25, 10])
    assert Carga.objects.filter(procesada=False).count() == 1
    consumir_novedades_carga()
    refrescar_data()
    assert mesa_categoria_2_2.status == MesaCategoria.STATUS.total_consolidada_dc
    assert fiscal_1.troll
    assert fiscal_1.scoring_troll() == 60
    assert Carga.objects.filter(invalidada=True).count() == 3
    assert Carga.objects.filter(procesada=False).count() == 3
    for carga in Carga.objects.filter(fiscal=fiscal_1):
        assert carga.invalidada and not carga.procesada

    # ahora lanzo una nueva consolidacion, que deberia procesar las cargas invalidadas
    # me fijo que el estado de cada MC quede como lo espero
    # la unica que cambio es la (1,2).
    # La (1,1) y la (2,2) no dependen de la carga del troll para quedar confirmadas
    # En la (2,1) no participo el troll
    consumir_novedades_carga()
    refrescar_data()
    assert mesa_categoria_1_1.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mesa_categoria_1_2.status == MesaCategoria.STATUS.total_sin_consolidar
    assert mesa_categoria_2_1.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mesa_categoria_2_2.status == MesaCategoria.STATUS.total_consolidada_dc
    assert Carga.objects.filter(invalidada=True).count() == 3
    assert Carga.objects.filter(procesada=False).count() == 0
    for carga in Carga.objects.filter(fiscal=fiscal_1):
        assert carga.invalidada


def test_cargas_troll_no_consolidadas(db, settings):
    """
    Se verifica que luego de que un fiscal es detectado como troll,
    el estado de las cargas "en conflicto" o "sin consolidar" en las que participó cambie adecuadamente
    """

    settings.SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL = 50
    settings.MIN_COINCIDENCIAS_CARGAS = 2

    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    fiscal_3 = nuevo_fiscal()
    fiscal_4 = nuevo_fiscal()
    fiscal_5 = nuevo_fiscal()
    categoria_1 = nueva_categoria(["o1", "o2", "o3"])
    categoria_2 = nueva_categoria(["p1", "p2", "p3", "p4"])

    mesa_1 = MesaFactory(categorias=[categoria_1, categoria_2])
    mesa_2 = MesaFactory(categorias=[categoria_1, categoria_2])
    mesa_3 = MesaFactory(categorias=[categoria_1, categoria_2])
    mesa_4 = MesaFactory(categorias=[categoria_1])
    mesa_categoria_1_1 = MesaCategoria.objects.filter(mesa=mesa_1, categoria=categoria_1).first()
    mesa_categoria_1_2 = MesaCategoria.objects.filter(mesa=mesa_1, categoria=categoria_2).first()
    mesa_categoria_2_1 = MesaCategoria.objects.filter(mesa=mesa_2, categoria=categoria_1).first()
    mesa_categoria_2_2 = MesaCategoria.objects.filter(mesa=mesa_2, categoria=categoria_2).first()
    mesa_categoria_3_1 = MesaCategoria.objects.filter(mesa=mesa_3, categoria=categoria_1).first()
    mesa_categoria_3_2 = MesaCategoria.objects.filter(mesa=mesa_3, categoria=categoria_2).first()
    mesa_categoria_4_1 = MesaCategoria.objects.filter(mesa=mesa_4, categoria=categoria_1).first()

    carga_1_1_1 = nueva_carga(mesa_categoria_1_1, fiscal_1, [20, 25, 15])  # 20 de diferencia
    carga_1_1_2 = nueva_carga(mesa_categoria_1_1, fiscal_2, [30, 20, 10])
    carga_1_1_3 = nueva_carga(mesa_categoria_1_1, fiscal_3, [30, 20, 10])
    carga_1_2_1 = nueva_carga(mesa_categoria_1_2, fiscal_1, [30, 15, 15, 10])
    carga_1_2_3 = nueva_carga(mesa_categoria_1_2, fiscal_3, [30, 15, 10, 5])
    carga_1_2_4 = nueva_carga(mesa_categoria_1_2, fiscal_4, [30, 18, 7, 5])
    carga_2_1_2 = nueva_carga(mesa_categoria_2_1, fiscal_2, [60, 25, 20])
    carga_2_1_4 = nueva_carga(mesa_categoria_2_1, fiscal_4, [60, 30, 15])
    carga_2_2_1 = nueva_carga(mesa_categoria_2_2, fiscal_1, [60, 20, 18, 7])  # 40 de diferencia
    carga_2_2_4 = nueva_carga(mesa_categoria_2_2, fiscal_4, [40, 30, 25, 10])
    carga_3_1_1 = nueva_carga(mesa_categoria_3_1, fiscal_1, [25, 15, 20])
    carga_3_1_5 = nueva_carga(mesa_categoria_3_1, fiscal_5, [28, 12, 20])
    carga_3_2_1 = nueva_carga(mesa_categoria_3_2, fiscal_1, [60, 20, 18, 7])
    carga_4_1_2 = nueva_carga(mesa_categoria_4_1, fiscal_2, [60, 25, 20])

    def refrescar_data():
        for mesa_categoria in [
            mesa_categoria_1_1, mesa_categoria_1_2, mesa_categoria_2_1, mesa_categoria_2_2,
            mesa_categoria_3_1, mesa_categoria_3_2, mesa_categoria_4_1
        ]:
            mesa_categoria.refresh_from_db()
        for fiscal in [fiscal_1, fiscal_2, fiscal_3, fiscal_4, fiscal_5]:
            fiscal.refresh_from_db()

    assert Carga.objects.filter(procesada=False).count() == 14
    assert Carga.objects.filter(invalidada=True).count() == 0
    assert not fiscal_1.troll

    # hasta aca: (1,1) consolidada; (3,2) y (4,1) sin consolidar; (1,2), (2,1), (2,2), (3,1) en conflicto
    # fiscal_1 tiene 20 de scoring troll
    consumir_novedades_carga()
    refrescar_data()
    assert mesa_categoria_1_1.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mesa_categoria_1_2.status == MesaCategoria.STATUS.total_en_conflicto
    assert mesa_categoria_2_1.status == MesaCategoria.STATUS.total_en_conflicto
    assert mesa_categoria_2_2.status == MesaCategoria.STATUS.total_en_conflicto
    assert mesa_categoria_3_1.status == MesaCategoria.STATUS.total_en_conflicto
    assert mesa_categoria_3_2.status == MesaCategoria.STATUS.total_sin_consolidar
    assert mesa_categoria_4_1.status == MesaCategoria.STATUS.total_sin_consolidar
    assert fiscal_1.scoring_troll() == 20
    assert not fiscal_1.troll
    assert Carga.objects.filter(procesada=False).count() == 0
    assert Carga.objects.filter(invalidada=True).count() == 0

    # ahora hago una carga que confirma la MC (2,2). Esto tiene que desencadenar que
    # - el fiscal 1 se detecta como troll
    # - sus cargas pasan a invalidadas y pendientes de proceso
    carga_2_2_5 = nueva_carga(mesa_categoria_2_2, fiscal_5, [40, 30, 25, 10])
    assert Carga.objects.filter(procesada=False).count() == 1
    consumir_novedades_carga()
    refrescar_data()
    assert mesa_categoria_2_2.status == MesaCategoria.STATUS.total_consolidada_dc
    assert fiscal_1.troll
    assert fiscal_1.scoring_troll() == 60
    assert Carga.objects.filter(invalidada=True).count() == 5
    assert Carga.objects.filter(procesada=False).count() == 5
    for carga in Carga.objects.filter(fiscal=fiscal_1):
        assert carga.invalidada and not carga.procesada

    # ahora lanzo una nueva consolidacion, que deberia procesar las cargas invalidadas
    # me fijo que el estado de cada MC quede como lo espero
    # cambian (3,1) y (3,2).
    # La (1,1) y la (2,2) no dependen de la carga del troll para quedar confirmadas
    # En (1,2) sigue estando en conflicto
    # En (2,1) y en (4,1) y no participo el troll
    consumir_novedades_carga()
    refrescar_data()
    assert mesa_categoria_1_1.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mesa_categoria_1_2.status == MesaCategoria.STATUS.total_en_conflicto
    assert mesa_categoria_2_1.status == MesaCategoria.STATUS.total_en_conflicto
    assert mesa_categoria_2_2.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mesa_categoria_3_1.status == MesaCategoria.STATUS.total_sin_consolidar
    assert mesa_categoria_3_2.status == MesaCategoria.STATUS.sin_cargar
    assert mesa_categoria_4_1.status == MesaCategoria.STATUS.total_sin_consolidar
    assert Carga.objects.filter(invalidada=True).count() == 5
    assert Carga.objects.filter(procesada=False).count() == 0
    for carga in Carga.objects.filter(fiscal=fiscal_1):
        assert carga.invalidada


def test_cargas_troll_con_problemas(db, settings):
    """
    Se verifica que luego de que un fiscal es detectado como troll,
    el estado de las cargas "con problemas" en las que participó cambie adecuadamente
    """
    settings.MIN_COINCIDENCIAS_CARGAS = 2
    settings.MIN_COINCIDENCIAS_CARGAS_PROBLEMA = 2

    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    fiscal_3 = nuevo_fiscal()
    categoria_1 = nueva_categoria(["o1", "o2", "o3"])

    mesa_1 = MesaFactory(categorias=[categoria_1])
    mesa_2 = MesaFactory(categorias=[categoria_1])
    mesa_categoria_1_1 = MesaCategoria.objects.filter(mesa=mesa_1, categoria=categoria_1).first()
    mesa_categoria_2_1 = MesaCategoria.objects.filter(mesa=mesa_2, categoria=categoria_1).first()

    carga_1_1_1 = nueva_carga(mesa_categoria_1_1, fiscal_1, [20, 25, 15])
    carga_1_1_2 = reportar_problema_mesa_categoria(mesa_categoria_1_1, fiscal_2)
    carga_2_1_1 = reportar_problema_mesa_categoria(mesa_categoria_2_1, fiscal_1)
    carga_2_1_3 = nueva_carga(mesa_categoria_2_1, fiscal_3, [60, 30, 15])

    def refrescar_data():
        for db_object in [mesa_categoria_1_1, mesa_categoria_2_1, fiscal_1, fiscal_2, fiscal_3]:
            db_object.refresh_from_db()

    assert Carga.objects.filter(procesada=False).count() == 4
    assert Carga.objects.filter(invalidada=True).count() == 0
    assert not fiscal_1.troll

    # hasta aca: (1,1) y (2,1) sin consolidar, tienen problemas pero no la cantidad necesaria
    consumir_novedades_carga()
    refrescar_data()
    assert mesa_categoria_1_1.status == MesaCategoria.STATUS.total_sin_consolidar
    assert mesa_categoria_2_1.status == MesaCategoria.STATUS.total_sin_consolidar
    assert Carga.objects.filter(procesada=False).count() == 0
    assert Carga.objects.filter(invalidada=True).count() == 0

    # ahora digo de prepo que el fiscal 1 es troll
    # Por lo tanto sus cargas pasan a invalidadas y pendientes de proceso
    fiscal_1.marcar_como_troll(fiscal_3)
    assert fiscal_1.troll
    assert Carga.objects.filter(invalidada=True).count() == 2
    assert Carga.objects.filter(procesada=False).count() == 2
    for carga in Carga.objects.filter(fiscal=fiscal_1):
        assert carga.invalidada and not carga.procesada

    # ahora lanzo una nueva consolidacion, que deberia procesar las cargas invalidadas
    # La (1,1) queda sin_cargar, porque la única carga válida es un problema
    # La (2,1) sigue sin_consolidar
    consumir_novedades_carga()
    refrescar_data()
    assert mesa_categoria_1_1.status == MesaCategoria.STATUS.sin_cargar
    assert mesa_categoria_2_1.status == MesaCategoria.STATUS.total_sin_consolidar
    assert Carga.objects.filter(invalidada=True).count() == 2
    assert Carga.objects.filter(procesada=False).count() == 0
    assert mesa_categoria_2_1.carga_testigo == carga_2_1_3
    for carga in Carga.objects.filter(fiscal=fiscal_1):
        assert carga.invalidada


def test_identificaciones_troll(db, settings):
    """
    Se verifica que luego de que un fiscal es detectado como troll,
    el estado asociado a las identificaciones que hubiera hecho cambia tal cual se espera.
    """

    settings.SCORING_TROLL_IDENTIFICACION_DISTINTA_A_CONFIRMADA = 180
    settings.SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL = 50
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2

    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    fiscal_3 = nuevo_fiscal()
    fiscal_4 = nuevo_fiscal()
    fiscal_5 = nuevo_fiscal()
    categoria_1 = nueva_categoria(["o1", "o2", "o3"])

    mesa_1 = MesaFactory(categorias=[categoria_1])
    mesa_2 = MesaFactory(categorias=[categoria_1])
    mesa_3 = MesaFactory(categorias=[categoria_1])
    mesa_4 = MesaFactory(categorias=[categoria_1])
    mesa_categoria_1 = MesaCategoria.objects.filter(mesa=mesa_1, categoria=categoria_1).first()
    mesa_categoria_2 = MesaCategoria.objects.filter(mesa=mesa_2, categoria=categoria_1).first()
    attach_1 = AttachmentFactory()
    attach_2 = AttachmentFactory()
    attach_3 = AttachmentFactory()
    attach_4 = AttachmentFactory()

    def refrescar_data():
        for db_object in [
            mesa_categoria_1, mesa_categoria_2,
            attach_1, attach_2, attach_3, attach_4,
            fiscal_1, fiscal_2, fiscal_3, fiscal_4, fiscal_5
        ]:
            db_object.refresh_from_db()

    identificar(attach_1, mesa_1, fiscal_1)
    identificar(attach_1, mesa_1, fiscal_2)
    identificar(attach_2, mesa_2, fiscal_2)
    identificar(attach_2, mesa_2, fiscal_3)
    identificar(attach_3, mesa_1, fiscal_1)
    identificar(attach_3, mesa_4, fiscal_3)
    identificar(attach_4, mesa_1, fiscal_1)
    identificar(attach_4, mesa_4, fiscal_2)
    nueva_carga(mesa_categoria_1, fiscal_3, [20, 25, 15])
    nueva_carga(mesa_categoria_1, fiscal_4, [20, 25, 15])
    nueva_carga(mesa_categoria_2, fiscal_4, [60, 25, 20])
    nueva_carga(mesa_categoria_2, fiscal_5, [60, 25, 20])

    assert Identificacion.objects.filter(procesada=False).count() == 8
    assert Identificacion.objects.filter(invalidada=True).count() == 0
    assert Carga.objects.filter(procesada=False).count() == 4
    assert Carga.objects.filter(invalidada=True).count() == 0

    # hasta aca: a1, a2 identificada; a3, a4 sin identificar.
    consumir_novedades_identificacion()
    consumir_novedades_carga()
    refrescar_data()
    assert attach_1.status == Attachment.STATUS.identificada
    assert attach_2.status == Attachment.STATUS.identificada
    assert attach_3.status == Attachment.STATUS.sin_identificar
    assert attach_4.status == Attachment.STATUS.sin_identificar
    assert mesa_categoria_1.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mesa_categoria_1.carga_testigo is not None
    assert mesa_categoria_1.orden_de_carga is not None
    assert mesa_categoria_2.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mesa_categoria_2.carga_testigo is not None
    assert mesa_categoria_2.orden_de_carga is not None
    assert not fiscal_1.troll
    assert Identificacion.objects.filter(procesada=False).count() == 0
    assert Identificacion.objects.filter(invalidada=True).count() == 0
    assert Carga.objects.filter(procesada=False).count() == 0
    assert Carga.objects.filter(invalidada=True).count() == 0

    identificar(attach_4, mesa_4, fiscal_4)

    # al consolidar esta identificacion, el fiscal 1 pasa a ser troll
    # las identificaciones del fiscal 1 se invalidan
    consumir_novedades_identificacion()
    refrescar_data()
    assert attach_1.status == Attachment.STATUS.identificada
    assert attach_2.status == Attachment.STATUS.identificada
    assert attach_3.status == Attachment.STATUS.sin_identificar
    assert attach_4.status == Attachment.STATUS.identificada
    assert mesa_categoria_1.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mesa_categoria_1.carga_testigo is not None
    assert mesa_categoria_1.orden_de_carga is not None
    assert mesa_categoria_2.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mesa_categoria_2.carga_testigo is not None
    assert mesa_categoria_2.orden_de_carga is not None
    assert fiscal_1.troll
    assert Identificacion.objects.filter(procesada=False).count() == 3
    assert Identificacion.objects.filter(invalidada=True).count() == 3
    for ident in Identificacion.objects.filter(fiscal=fiscal_1):
        assert ident.invalidada
    assert Carga.objects.filter(procesada=False).count() == 0
    assert Carga.objects.filter(invalidada=True).count() == 0

    # se corre otra consolidacion de identificaciones
    # a1 pasa a sin_identificar, se invalidan las cargas de m1 y se le borra el orden de carga
    consumir_novedades_identificacion()
    refrescar_data()
    assert attach_1.status == Attachment.STATUS.sin_identificar
    assert attach_2.status == Attachment.STATUS.identificada
    assert attach_3.status == Attachment.STATUS.sin_identificar
    assert attach_4.status == Attachment.STATUS.identificada
    assert mesa_categoria_1.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mesa_categoria_1.carga_testigo is not None
    assert mesa_categoria_1.orden_de_carga is None
    assert mesa_categoria_2.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mesa_categoria_2.carga_testigo is not None
    assert mesa_categoria_2.orden_de_carga is not None
    assert fiscal_1.troll
    assert Identificacion.objects.filter(procesada=False).count() == 0
    assert Identificacion.objects.filter(invalidada=True).count() == 3
    assert Carga.objects.filter(procesada=False).count() == 2
    assert Carga.objects.filter(invalidada=True).count() == 2
    for carga in Carga.objects.filter(mesa_categoria=mesa_categoria_1):
        assert carga.invalidada

    # finalmente, se ejecuta una consolidacion de cargas
    # la MesaCategoria de m1 pasa a sin_cargas, y se le borra la carga testigo
    consumir_novedades_carga()
    refrescar_data()
    assert mesa_categoria_1.status == MesaCategoria.STATUS.sin_cargar
    assert mesa_categoria_1.carga_testigo is None
    assert mesa_categoria_1.orden_de_carga is None
    assert mesa_categoria_2.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mesa_categoria_2.carga_testigo is not None
    assert mesa_categoria_2.orden_de_carga is not None
    assert fiscal_1.troll
    assert Identificacion.objects.filter(procesada=False).count() == 0
    assert Identificacion.objects.filter(invalidada=True).count() == 3
    assert Carga.objects.filter(procesada=False).count() == 0
    assert Carga.objects.filter(invalidada=True).count() == 2
    for carga in Carga.objects.filter(mesa_categoria=mesa_categoria_1):
        assert carga.invalidada


def test_carga_parcial_consolidada_dc(db, settings):
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    presi = CategoriaFactory()
    mesa_1 = MesaFactory(categorias=[presi])
    mesa_categoria_1 = MesaCategoria.objects.filter(mesa=mesa_1, categoria=presi).first()
    attach_1 = AttachmentFactory()

    assert mesa_categoria_1.status == MesaCategoria.STATUS.sin_cargar

    identificar(attach_1, mesa_1, fiscal_1)
    identificar(attach_1, mesa_1, fiscal_2)

    refrescar_data([presi, fiscal_1, fiscal_2, mesa_1, mesa_categoria_1, attach_1])

    assert not fiscal_1.troll
    assert not fiscal_2.troll

    assert Identificacion.objects.filter(procesada=False).count() == 2

    consumir_novedades_identificacion()
    refrescar_data([mesa_categoria_1, mesa_1, attach_1])

    assert Identificacion.objects.filter(procesada=False).count() == 0

    nueva_carga(mesa_categoria_1, fiscal_1, [20, 15], Carga.TIPOS.parcial)
    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1])
    assert mesa_categoria_1.status == MesaCategoria.STATUS.parcial_sin_consolidar

    nueva_carga(mesa_categoria_1, fiscal_2, [20, 15], Carga.TIPOS.parcial)
    refrescar_data([mesa_categoria_1])
    assert Carga.objects.filter(procesada=False).count() == 1

    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1])

    assert mesa_categoria_1.status == MesaCategoria.STATUS.parcial_consolidada_dc
    assert Carga.objects.filter(procesada=False).count() == 0


def test_troll_parcial_dc_a_sin_consolidar(db, settings):
    settings.SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL = 20
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    presi = CategoriaFactory()
    mesa_1 = MesaFactory(categorias=[presi])
    mesa_categoria_1 = MesaCategoria.objects.filter(mesa=mesa_1, categoria=presi).first()
    attach_1 = AttachmentFactory()
    identificar(attach_1, mesa_1, fiscal_1)
    identificar(attach_1, mesa_1, fiscal_2)

    refrescar_data([presi, fiscal_1, fiscal_2, mesa_1, mesa_categoria_1, attach_1])

    assert not fiscal_1.troll
    assert not fiscal_2.troll

    nueva_carga(mesa_categoria_1, fiscal_1, [20, 35], Carga.TIPOS.parcial)
    nueva_carga(mesa_categoria_1, fiscal_2, [20, 35], Carga.TIPOS.parcial)

    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1])

    assert mesa_categoria_1.status == MesaCategoria.STATUS.parcial_consolidada_dc
    assert Carga.objects.filter(invalidada=True).count() == 0

    fiscal_2.aplicar_marca_troll()
    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1, fiscal_2])

    assert mesa_categoria_1.status == MesaCategoria.STATUS.parcial_sin_consolidar
    assert Carga.objects.filter(invalidada=True).count() == 1


def test_troll_total_sin_consolidar_a_parcial_sin_consolidar(db, settings):
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    presi = CategoriaFactory()
    mesa_1 = MesaFactory(categorias=[presi])
    mesa_categoria_1 = MesaCategoria.objects.filter(mesa=mesa_1, categoria=presi).first()
    attach_1 = AttachmentFactory()
    identificar(attach_1, mesa_1, fiscal_1)
    identificar(attach_1, mesa_1, fiscal_2)

    refrescar_data([presi, fiscal_1, fiscal_2, mesa_1, mesa_categoria_1, attach_1])

    assert not fiscal_1.troll
    assert not fiscal_2.troll

    nueva_carga(mesa_categoria_1, fiscal_1, [20, 35], Carga.TIPOS.parcial)
    nueva_carga(mesa_categoria_1, fiscal_2, [20, 35], Carga.TIPOS.parcial)

    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1])

    assert mesa_categoria_1.status == MesaCategoria.STATUS.parcial_consolidada_dc

    nueva_carga(mesa_categoria_1, fiscal_2, [20, 35], Carga.TIPOS.total)

    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1])

    assert mesa_categoria_1.status == MesaCategoria.STATUS.total_sin_consolidar
    assert Carga.objects.filter(invalidada=True).count() == 0

    fiscal_2.aplicar_marca_troll()
    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1, fiscal_2])

    assert mesa_categoria_1.status == MesaCategoria.STATUS.parcial_sin_consolidar
    assert Carga.objects.filter(invalidada=True).count() == 2


def test_troll_total_consolidada_dc_a_sin_cargar(db, settings):
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    presi = CategoriaFactory()
    mesa_1 = MesaFactory(categorias=[presi])
    mesa_categoria_1 = MesaCategoria.objects.filter(mesa=mesa_1, categoria=presi).first()
    attach_1 = AttachmentFactory()
    identificar(attach_1, mesa_1, fiscal_1)
    identificar(attach_1, mesa_1, fiscal_2)

    refrescar_data([presi, fiscal_1, fiscal_2, mesa_1, mesa_categoria_1, attach_1])

    nueva_carga(mesa_categoria_1, fiscal_1, [20, 35], Carga.TIPOS.parcial)
    nueva_carga(mesa_categoria_1, fiscal_2, [20, 35], Carga.TIPOS.parcial)

    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1])

    nueva_carga(mesa_categoria_1, fiscal_2, [20, 35], Carga.TIPOS.total)
    nueva_carga(mesa_categoria_1, fiscal_1, [20, 35], Carga.TIPOS.total)

    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1])

    assert mesa_categoria_1.status == MesaCategoria.STATUS.total_consolidada_dc
    assert Carga.objects.filter(invalidada=True).count() == 0

    fiscal_2.aplicar_marca_troll()
    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1, fiscal_2])

    assert mesa_categoria_1.status == MesaCategoria.STATUS.sin_cargar
    assert Carga.objects.filter(invalidada=True).count() == 3


def test_troll_total_consolidada_dc_a_parcial_sin_consolidar(db, settings):
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    fiscal_3 = nuevo_fiscal()
    presi = CategoriaFactory()
    mesa_1 = MesaFactory(categorias=[presi])
    mesa_categoria_1 = MesaCategoria.objects.filter(mesa=mesa_1, categoria=presi).first()
    attach_1 = AttachmentFactory()
    identificar(attach_1, mesa_1, fiscal_1)
    identificar(attach_1, mesa_1, fiscal_3)

    refrescar_data([presi, fiscal_1, fiscal_2, fiscal_3, mesa_1, mesa_categoria_1, attach_1])

    nueva_carga(mesa_categoria_1, fiscal_1, [20, 35], Carga.TIPOS.parcial)
    nueva_carga(mesa_categoria_1, fiscal_2, [20, 35], Carga.TIPOS.parcial)

    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1])

    assert mesa_categoria_1.status == MesaCategoria.STATUS.parcial_consolidada_dc

    nueva_carga(mesa_categoria_1, fiscal_2, [20, 35], Carga.TIPOS.total)
    nueva_carga(mesa_categoria_1, fiscal_1, [20, 35], Carga.TIPOS.total)

    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1])

    assert mesa_categoria_1.status == MesaCategoria.STATUS.total_consolidada_dc
    assert Carga.objects.filter(invalidada=True).count() == 0

    fiscal_2.aplicar_marca_troll()
    consumir_novedades_identificacion()
    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1, fiscal_2])

    assert mesa_categoria_1.status == MesaCategoria.STATUS.parcial_sin_consolidar
    assert Carga.objects.filter(invalidada=True).count() == 2


def test_troll_total_consolidada_dc_a_total_sin_consolidar(db, settings):
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    fiscal_3 = nuevo_fiscal()
    presi = CategoriaFactory()
    mesa_1 = MesaFactory(categorias=[presi])
    mesa_categoria_1 = MesaCategoria.objects.filter(mesa=mesa_1, categoria=presi).first()
    attach_1 = AttachmentFactory()
    identificar(attach_1, mesa_1, fiscal_1)
    identificar(attach_1, mesa_1, fiscal_2)

    refrescar_data([presi, fiscal_1, fiscal_2, fiscal_3, mesa_1, mesa_categoria_1, attach_1])

    assert not fiscal_1.troll
    assert not fiscal_2.troll

    nueva_carga(mesa_categoria_1, fiscal_1, [20, 35], Carga.TIPOS.parcial)
    nueva_carga(mesa_categoria_1, fiscal_2, [20, 35], Carga.TIPOS.parcial)

    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1])

    assert mesa_categoria_1.status == MesaCategoria.STATUS.parcial_consolidada_dc

    nueva_carga(mesa_categoria_1, fiscal_3, [20, 35], Carga.TIPOS.total)
    nueva_carga(mesa_categoria_1, fiscal_1, [20, 35], Carga.TIPOS.total)

    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1])

    assert mesa_categoria_1.status == MesaCategoria.STATUS.total_consolidada_dc
    assert Carga.objects.filter(invalidada=True).count() == 0

    fiscal_3.aplicar_marca_troll()
    consumir_novedades_identificacion()
    consumir_novedades_carga()
    refrescar_data([mesa_categoria_1, fiscal_3])

    assert mesa_categoria_1.status == MesaCategoria.STATUS.total_sin_consolidar
    assert Carga.objects.filter(invalidada=True).count() == 1


def refrescar_data(objetos):
    for db_object in objetos:
        db_object.refresh_from_db()
