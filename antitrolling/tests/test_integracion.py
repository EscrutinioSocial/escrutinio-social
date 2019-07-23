import pytest

from django.conf import settings

from elecciones.models import MesaCategoria, Carga
from adjuntos.consolidacion import consolidar_identificaciones, consolidar_cargas, consumir_novedades_carga
from antitrolling.models import EventoScoringTroll
from elecciones.tests.factories import (
    MesaFactory, AttachmentFactory
)

from .utils_para_test import (
    nuevo_fiscal, identificar, reportar_problema_attachment,
    nueva_categoria, nueva_carga, reportar_problema_mesa_categoria
)


def test_asociacion_attachment_con_antitrolling(db):
    """
    Se simula que se asocia un Attachment a una mesa, usando la función de consolidación.
    Se comprueba que el efecto sobre el scoring de troll de los fiscales que hicieron identificaciones es el correcto.
    """

    settings.SCORING_TROLL_IDENTIFICACION_DISTINTA_A_CONFIRMADA = 180
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2
    settings.MIN_COINCIDENCIAS_IDENTIFICACION_PROBLEMA = 2

    fiscal1 = nuevo_fiscal()
    fiscal2 = nuevo_fiscal()
    fiscal3 = nuevo_fiscal()
    fiscal4 = nuevo_fiscal()
    mesa1 = MesaFactory()
    mesa2 = MesaFactory()
    attach = AttachmentFactory()
    
    # empezamos con dos identificaciones a mesas distintas
    identificar(attach, mesa1, fiscal1)
    identificar(attach, mesa2, fiscal3)
    # hasta aca no debería asociarse la mesa, ergo no se afecta el scoring troll de ningun fiscal
    consolidar_identificaciones(attach)
    for fiscal in [fiscal1, fiscal2, fiscal3, fiscal4]:
      assert fiscal.scoring_troll() == 0

    # se agregan dos nuevas identificaciones: el fiscal 2 identifica la misma mesa que el 1, el fiscal 4 reporta un problema
    identificar(attach, mesa1, fiscal2)
    reportar_problema_attachment(attach, fiscal4)
    # ahora si deberia asociarse la mesa, y como consecuencia, 
    # aumentar el scoring troll para los fiscales 3 y 4 que identificaron distinto a lo que se decidio
    consolidar_identificaciones(attach)
    assert fiscal1.scoring_troll() == 0
    assert fiscal2.scoring_troll() == 0
    assert fiscal3.scoring_troll() == 180
    assert fiscal4.scoring_troll() == 180


def test_confirmacion_carga_total_mesa_categoria_con_antitrolling(db):
    """
    Se simula que se confirma la carga total de una MesaCategoria, usando la función de consolidación.
    Se comprueba que el efecto sobre el scoring de troll de los fiscales que hicieron cargas es el correcto.
    Nota: la funcion auxiliar nueva_carga agrega una carga de tipo total.
    """

    settings.MIN_COINCIDENCIAS_CARGAS = 2
    settings.MIN_COINCIDENCIAS_CARGAS_PROBLEMA = 2
    settings.SCORING_TROLL_PROBLEMA_MESA_CATEGORIA_CON_CARGA_CONFIRMADA = 150

    # escenario
    fiscal1 = nuevo_fiscal()
    fiscal2 = nuevo_fiscal()
    fiscal3 = nuevo_fiscal()
    fiscal4 = nuevo_fiscal()
    fiscal5 = nuevo_fiscal()
    categoria = nueva_categoria(["o1", "o2", "o3"])
    mesa = MesaFactory(categorias=[categoria])
    mesa_categoria = MesaCategoria.objects.filter(mesa=mesa).first()

    # entran cuatro cargas: tres con resultados diferentes, una que marca un problema
    carga1 = nueva_carga(mesa_categoria, fiscal1, [32, 20, 10])
    carga2 = nueva_carga(mesa_categoria, fiscal2, [30, 20, 10])
    carga3 = nueva_carga(mesa_categoria, fiscal3, [5, 40, 15])
    carga4 = reportar_problema_mesa_categoria(mesa_categoria, fiscal4)
    # la consolidacion no deberia afectar el scoring de ningun fiscal, porque la mesa_categoria no queda consolidada
    consolidar_cargas(mesa_categoria)
    for fiscal in [fiscal1, fiscal2, fiscal3, fiscal4, fiscal5]:
      assert fiscal.scoring_troll() == 0

    # entra una quinta carga, coincidente con la segunda
    carga5 = nueva_carga(mesa_categoria, fiscal5, [30, 20, 10])
    # ahora la mesa_categoria queda consolidada, y por lo tanto, deberia afectarse el scoring de los fiscales
    # cuya carga no coincide con la aceptada
    consolidar_cargas(mesa_categoria)
    assert fiscal1.scoring_troll() == 2
    assert fiscal2.scoring_troll() == 0
    assert fiscal3.scoring_troll() == 50
    assert fiscal4.scoring_troll() == 150
    assert fiscal5.scoring_troll() == 0


def test_carga_confirmada_troll_vuelve_a_sin_consolidar(db):
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
    assert fiscal_1.troll == False

    # hasta aca: (1,1), (1,2) y (2,1) consolidadas, (2,2) en conflicto, fiscal_1 tiene 20 de scoring troll
    consumir_novedades_carga()
    refrescar_data()
    for mesa_categoria in [mesa_categoria_1_1, mesa_categoria_1_2, mesa_categoria_2_1]:
        assert mesa_categoria.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mesa_categoria_2_2.status == MesaCategoria.STATUS.total_en_conflicto
    assert fiscal_1.scoring_troll() == 20
    assert fiscal_1.troll == False
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
    assert fiscal_1.troll == True
    assert fiscal_1.scoring_troll() == 60
    assert Carga.objects.filter(invalidada=True).count() == 3
    assert Carga.objects.filter(procesada=False).count() == 3
    assert all(map(lambda carga: carga.invalidada and not carga.procesada, Carga.objects.filter(fiscal=fiscal_1).all()))

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
    assert all(map(lambda carga: carga.invalidada, Carga.objects.filter(fiscal=fiscal_1).all()))

    
