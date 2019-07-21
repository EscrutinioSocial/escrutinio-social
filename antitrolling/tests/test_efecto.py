import pytest

from django.conf import settings

from elecciones.models import MesaCategoria, Carga
from antitrolling.efecto import (
  efecto_scoring_troll_asociacion_attachment, efecto_scoring_troll_confirmacion_carga,
  diferencia_opciones
)
from antitrolling.models import EventoScoringTroll
from elecciones.tests.factories import (
    MesaFactory, AttachmentFactory
)

from .utils_para_test import (
  nuevo_fiscal, identificar, reportar_problema_attachment,
  nueva_categoria, nueva_carga
)



def test_efecto_consolidar_asociacion_attachment(db):
    """
    Se comprueba que el efecto de afectar el scoring de troll a partir de la asociacion 
    de un Attachment a una Mesa sea el correcto.
    O sea, que se aumente el scoring de los fiscales que hicieron identificaciones distintas
    a la aceptada, y que no aumente el scoring de los fiscales que hicieron la identificacion aceptada.
    """

    settings.SCORING_TROLL_IDENTIFICACION_DISTINTA_A_CONFIRMADA = 180
    fiscal1 = nuevo_fiscal()
    fiscal2 = nuevo_fiscal()
    fiscal3 = nuevo_fiscal()
    fiscal4 = nuevo_fiscal()
    mesa1 = MesaFactory()
    mesa2 = MesaFactory()
    attach = AttachmentFactory()
    # los cuatro fiscales hacen una identificacion sobre el mismo attachment
    # los fiscales 1 y 2 hacen la identificacion que se va a aceptar, a la mesa 1
    # el fiscal 3 identifica a una mesa distinta
    # el fiscal 4 reporta un problema
    identificar(attach, mesa1, fiscal1)
    identificar(attach, mesa1, fiscal2)
    identificar(attach, mesa2, fiscal3)
    reportar_problema_attachment(attach, fiscal4)

    # se espera que se generen dos eventos, para los fiscales 3 y 4 que identificaron distinto
    # a la mesa que se indica como asociada al attachment
    cantidad_eventos_antes = EventoScoringTroll.objects.count()
    efecto_scoring_troll_asociacion_attachment(attach, mesa1)
    assert EventoScoringTroll.objects.count() == cantidad_eventos_antes + 2
    assert fiscal1.scoring_troll() == 0
    assert fiscal2.scoring_troll() == 0
    assert fiscal3.scoring_troll() == 180
    assert fiscal4.scoring_troll() == 180


def test_diferencia_opciones(db):
    # creo fiscales
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()

    # creo opciones y categoria
    categoria = nueva_categoria(["o1", "o2", "o3"])

    # creo mesa y mesa_categoria
    mesa = MesaFactory(categorias=[categoria])
    mesa_categoria = MesaCategoria.objects.filter(mesa=mesa).first()

    # creo cargas
    carga_1 = nueva_carga(mesa_categoria, fiscal_1, [30, 20, 10])
    carga_2 = nueva_carga(mesa_categoria, fiscal_2, [28, 19, 11])

    # calculo
    assert diferencia_opciones(carga_1, carga_2) == 4


def test_efecto_confirmar_carga_mesa_categoria(db):
    """
    Se comprueba que el efecto de afectar el scoring de troll 
    a partir de la confirmacion de la carga de una mesa_categoria sea el correcto.
    O sea, que se aumente el scoring de los fiscales que cargaron valores distintos a los aceptados,
    y que no aumente el scoring de los fiscales que hicieron la identificacion aceptada.
    """

    # escenario
    fiscal1 = nuevo_fiscal()
    fiscal2 = nuevo_fiscal()
    fiscal3 = nuevo_fiscal()
    fiscal4 = nuevo_fiscal()
    categoria = nueva_categoria(["o1", "o2", "o3"])
    mesa = MesaFactory(categorias=[categoria])
    mesa_categoria = MesaCategoria.objects.filter(mesa=mesa).first()

    # simulo que se hacen cuatro cargas, tengo que pedir explicitamente que se actualice la firma
    # (lo hace la UI de carga)
    carga1 = nueva_carga(mesa_categoria, fiscal1, [32, 20, 10])
    carga2 = nueva_carga(mesa_categoria, fiscal2, [30, 20, 10])
    carga3 = nueva_carga(mesa_categoria, fiscal3, [5, 40, 15])
    carga4 = nueva_carga(mesa_categoria, fiscal4, [30, 20, 10])
    for carga in [carga1, carga2, carga3, carga4]:
      carga.actualizar_firma()

    # se define que las cargas de fiscal2 y fiscal4 son las correctas
    mesa_categoria.actualizar_status(MesaCategoria.STATUS.total_consolidada_dc, carga2)

    # antes de afectar el scoring troll: los cuatro fiscales tienen scoring 0
    for fiscal in [fiscal1, fiscal2, fiscal3, fiscal4]:
      assert fiscal.scoring_troll() == 0

    # hago la afectacion de scoring trol
    efecto_scoring_troll_confirmacion_carga(mesa_categoria)

    # ahora los fiscales que cargaron distinto a lo aceptado deberian tener mas scoring, el resto no
    assert fiscal1.scoring_troll() == 2
    assert fiscal2.scoring_troll() == 0
    assert fiscal3.scoring_troll() == 50
    assert fiscal4.scoring_troll() == 0

    
