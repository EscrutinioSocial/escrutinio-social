import pytest

from django.conf import settings

from elecciones.models import MesaCategoria
from antitrolling.efecto import efecto_scoring_troll_asociacion_attachment, diferencia_opciones
from antitrolling.models import EventoScoringTroll
from elecciones.tests.factories import (
    MesaFactory, AttachmentFactory, 
    OpcionFactory, CategoriaFactory, CargaFactory, VotoMesaReportadoFactory
)

from utils_para_test import nuevo_fiscal, identificar, reportar_problema_attachment


@pytest.mark.django_db
def test_efecto_consolidar_asociacion_attachment():
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


def nueva_categoria():
    opcion_1 = OpcionFactory(nombre="o1")
    opcion_2 = OpcionFactory(nombre="o2")
    opcion_3 = OpcionFactory(nombre="o3")
    return CategoriaFactory(opciones=[opcion_1, opcion_2, opcion_3])


def nueva_carga(mesa_categoria, fiscal, votos_opcion_1, votos_opcion_2, votos_opcion_3):
  carga = CargaFactory(mesa_categoria=mesa_categoria, fiscal=fiscal)
  VotoMesaReportadoFactory(carga=carga, opcion=mesa_categoria.categoria.opciones.filter(nombre="o1").first(), votos=votos_opcion_1)
  VotoMesaReportadoFactory(carga=carga, opcion=mesa_categoria.categoria.opciones.filter(nombre="o2").first(), votos=votos_opcion_2)
  VotoMesaReportadoFactory(carga=carga, opcion=mesa_categoria.categoria.opciones.filter(nombre="o3").first(), votos=votos_opcion_3)
  return carga


@pytest.mark.django_db
def test_diferencia_opciones():
    # creo fiscales
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()

    # creo opciones y categoria
    categoria = nueva_categoria()

    # creo mesa y mesa_categoria
    mesa = MesaFactory(categorias=[categoria])
    mesa_categoria = MesaCategoria.objects.filter(mesa=mesa).first()

    # creo cargas
    carga_1 = nueva_carga(mesa_categoria, fiscal_1, 30, 20, 10)
    carga_2 = nueva_carga(mesa_categoria, fiscal_2, 28, 19, 11)

    # calculo
    assert diferencia_opciones(carga_1, carga_2) == 4
