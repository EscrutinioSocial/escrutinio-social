import pytest

from django.conf import settings

from elecciones.models import MesaCategoria, Carga
from adjuntos.consolidacion import consolidar_identificaciones, consolidar_cargas
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

