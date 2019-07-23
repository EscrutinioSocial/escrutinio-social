import pytest

from django.conf import settings

from elecciones.models import MesaCategoria, Carga
from adjuntos.models import Identificacion
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
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    fiscal_3 = nuevo_fiscal()
    fiscal_4 = nuevo_fiscal()
    mesa_1 = MesaFactory()
    mesa_2 = MesaFactory()
    attach = AttachmentFactory()
    # los cuatro fiscales hacen una identificacion sobre el mismo attachment
    # los fiscales 1 y 2 hacen la identificacion que se va a aceptar, a la mesa 1
    # el fiscal 3 identifica a una mesa distinta
    # el fiscal 4 reporta un problema
    identificar(attach, mesa_1, fiscal_1)
    identificar(attach, mesa_1, fiscal_2)
    identificar(attach, mesa_2, fiscal_3)
    reportar_problema_attachment(attach, fiscal_4)

    # se espera que se generen dos eventos, para los fiscales 3 y 4 que identificaron distinto
    # a la mesa que se indica como asociada al attachment
    cantidad_eventos_antes = EventoScoringTroll.objects.count()
    efecto_scoring_troll_asociacion_attachment(attach, mesa_1)
    assert EventoScoringTroll.objects.count() == cantidad_eventos_antes + 2
    assert fiscal_1.scoring_troll() == 0
    assert fiscal_2.scoring_troll() == 0
    assert fiscal_3.scoring_troll() == 180
    assert fiscal_4.scoring_troll() == 180


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
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    fiscal_3 = nuevo_fiscal()
    fiscal_4 = nuevo_fiscal()
    categoria = nueva_categoria(["o1", "o2", "o3"])
    mesa = MesaFactory(categorias=[categoria])
    mesa_categoria = MesaCategoria.objects.filter(mesa=mesa).first()

    # simulo que se hacen cuatro cargas, tengo que pedir explicitamente que se actualice la firma
    # (lo hace la UI de carga)
    carga1 = nueva_carga(mesa_categoria, fiscal_1, [32, 20, 10])
    carga2 = nueva_carga(mesa_categoria, fiscal_2, [30, 20, 10])
    carga3 = nueva_carga(mesa_categoria, fiscal_3, [5, 40, 15])
    carga4 = nueva_carga(mesa_categoria, fiscal_4, [30, 20, 10])
    for carga in [carga1, carga2, carga3, carga4]:
      carga.actualizar_firma()

    # se define que las cargas de fiscal_2 y fiscal_4 son las correctas
    mesa_categoria.actualizar_status(MesaCategoria.STATUS.total_consolidada_dc, carga2)

    # antes de afectar el scoring troll: los cuatro fiscales tienen scoring 0
    for fiscal in [fiscal_1, fiscal_2, fiscal_3, fiscal_4]:
      assert fiscal.scoring_troll() == 0

    # hago la afectacion de scoring trol
    efecto_scoring_troll_confirmacion_carga(mesa_categoria)

    # ahora los fiscales que cargaron distinto a lo aceptado deberian tener mas scoring, el resto no
    assert fiscal_1.scoring_troll() == 2
    assert fiscal_2.scoring_troll() == 0
    assert fiscal_3.scoring_troll() == 50
    assert fiscal_4.scoring_troll() == 0

    
def test_efecto_marcar_fiscal_como_troll(db):
    """
    Se comprueba que al marcar un fiscal como troll,
    las cargas e identificaciones que hizo quedan invalidadas.
    """
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    fiscal_3 = nuevo_fiscal()
    fiscal_4 = nuevo_fiscal()
    categoria_1 = nueva_categoria(["o1", "o2", "o3"])
    categoria_2 = nueva_categoria(["p1", "p2", "p3"])

    mesa_1 = MesaFactory(categorias=[categoria_1, categoria_2])
    mesa_2 = MesaFactory(categorias=[categoria_1, categoria_2])
    mesa_3 = MesaFactory(categorias=[categoria_1])
    attach_1 = AttachmentFactory()
    attach_2 = AttachmentFactory()
    attach_3 = AttachmentFactory()
    attach_4 = AttachmentFactory()

    ident_1_1 = identificar(attach_1, mesa_1, fiscal_1)
    ident_1_2 = identificar(attach_1, mesa_1, fiscal_2)
    ident_1_3 = reportar_problema_attachment(attach_1, fiscal_3)
    ident_2_2 = identificar(attach_2, mesa_2, fiscal_2)
    ident_2_3 = identificar(attach_2, mesa_3, fiscal_3)
    ident_3_1 = reportar_problema_attachment(attach_3, fiscal_1)
    ident_3_4 = identificar(attach_3, mesa_3, fiscal_4)
    ident_4_2 = identificar(attach_4, mesa_2, fiscal_2)
    ident_4_4 = reportar_problema_attachment(attach_4, fiscal_4)

    mesa_categoria_1_1 = MesaCategoria.objects.filter(mesa=mesa_1, categoria=categoria_1).first()
    carga_1_1_1 = nueva_carga(mesa_categoria_1_1, fiscal_1, [30, 20, 10])
    carga_1_1_2 = nueva_carga(mesa_categoria_1_1, fiscal_2, [30, 20, 10])
    mesa_categoria_1_2 = MesaCategoria.objects.filter(mesa=mesa_1, categoria=categoria_2).first()
    carga_1_2_1 = nueva_carga(mesa_categoria_1_2, fiscal_1, [30, 20, 10])
    carga_1_2_3 = nueva_carga(mesa_categoria_1_2, fiscal_3, [30, 20, 10])
    mesa_categoria_2_1 = MesaCategoria.objects.filter(mesa=mesa_2, categoria=categoria_1).first()
    carga_2_1_2 = nueva_carga(mesa_categoria_2_1, fiscal_2, [30, 20, 10])
    carga_2_1_3 = nueva_carga(mesa_categoria_2_1, fiscal_3, [30, 20, 10])
    mesa_categoria_2_2 = MesaCategoria.objects.filter(mesa=mesa_2, categoria=categoria_2).first()
    carga_2_2_1 = nueva_carga(mesa_categoria_2_2, fiscal_1, [30, 20, 10])
    carga_2_2_4 = nueva_carga(mesa_categoria_2_2, fiscal_4, [30, 20, 10])
    mesa_categoria_3_1 = MesaCategoria.objects.filter(mesa=mesa_3, categoria=categoria_1).first()
    carga_3_1_2 = nueva_carga(mesa_categoria_3_1, fiscal_2, [30, 20, 10])
    carga_2_2_4 = nueva_carga(mesa_categoria_3_1, fiscal_4, [30, 20, 10])

    assert not(any(map(lambda ident : ident.invalidada, Identificacion.objects.all())))
    assert not(any(map(lambda carga: carga.invalidada, Carga.objects.all())))


    
