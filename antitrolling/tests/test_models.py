import pytest

from django.conf import settings

from antitrolling.models import (
    EventoScoringTroll, CambioEstadoTroll,
    aumentar_scoring_troll_identificacion
)

from elecciones.tests.factories import (
    MesaFactory, AttachmentFactory
)

from utils_para_test import nuevo_fiscal, identificar, reportar_problema_attachment


@pytest.mark.django_db
def test_marcar_troll():
    fiscal = nuevo_fiscal()
    assert fiscal.troll == False
    fiscal.marcar_como_troll()
    assert fiscal.troll == True


@pytest.mark.django_db
def test_registro_evento_scoring_identificacion():
    """
    Se comprueba que un EventoScoringTroll se genere con los valores correctos.
    """

    fiscal = nuevo_fiscal()
    attach = AttachmentFactory()
    identi = reportar_problema_attachment(attach, fiscal)

    cantidad_eventos_antes = EventoScoringTroll.objects.count()
    aumentar_scoring_troll_identificacion(100, identi)
    assert EventoScoringTroll.objects.count() == cantidad_eventos_antes + 1
    assert fiscal.eventos_scoring_troll.count() == 1
    evento = fiscal.eventos_scoring_troll.first()
    assert evento.motivo == EventoScoringTroll.MOTIVO.identificacion_attachment_distinta_a_confirmada
    assert evento.mesa_categoria is None
    assert evento.attachment == attach
    assert evento.automatico == True
    assert evento.actor is None
    assert evento.fiscal_afectado == fiscal
    assert evento.variacion == 100



@pytest.mark.django_db
def test_registro_cambio_estado_troll():
    """
    Se comprueba que un CambioEstadoTroll se genere con los valores correctos.
    """

    settings.SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL = 320
    fiscal = nuevo_fiscal()
    attach1 = AttachmentFactory()
    attach2 = AttachmentFactory()
    identi1 = reportar_problema_attachment(attach1, fiscal)
    identi2 = reportar_problema_attachment(attach2, fiscal)

    cantidad_cambios_estado_antes = CambioEstadoTroll.objects.count()
    aumentar_scoring_troll_identificacion(200, identi1)
    assert CambioEstadoTroll.objects.count() == cantidad_cambios_estado_antes
    assert CambioEstadoTroll.objects.filter(fiscal_afectado = fiscal).count() == 0
    aumentar_scoring_troll_identificacion(200, identi2)
    assert CambioEstadoTroll.objects.count() == cantidad_cambios_estado_antes + 1
    cambioEstado = CambioEstadoTroll.objects.filter(fiscal_afectado = fiscal).first()
    assert cambioEstado.automatico == True
    assert cambioEstado.actor is None
    assert cambioEstado.evento_disparador == fiscal.eventos_scoring_troll.order_by('created').last()
    assert cambioEstado.troll == True



@pytest.mark.django_db
def test_aumentar_scrolling():
    """
    Se comprueba que al disparar eventos de aumento de scoring, el efecto sea el esperado
    """

    settings.SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL = 400
    fiscal1 = nuevo_fiscal()
    fiscal2 = nuevo_fiscal()
    assert fiscal1.scoring_troll() == 0
    assert fiscal2.scoring_troll() == 0

    mesa1 = MesaFactory()
    attach1 = AttachmentFactory()
    attach2 = AttachmentFactory()
    identi1 = identificar(attach1, mesa1, fiscal1)
    identi2 = identificar(attach1, mesa1, fiscal2)
    identi3 = identificar(attach2, mesa1, fiscal1)
    aumentar_scoring_troll_identificacion(100, identi1)
    aumentar_scoring_troll_identificacion(150, identi2)
    aumentar_scoring_troll_identificacion(250, identi3)
    assert fiscal1.scoring_troll() == 350
    assert fiscal2.scoring_troll() == 150
    assert fiscal1.troll == False
    assert fiscal2.troll == False

    attach3 = AttachmentFactory()
    identi4 = reportar_problema_attachment(attach3, fiscal1)
    aumentar_scoring_troll_identificacion(80, identi4)
    assert fiscal1.scoring_troll() == 430
    assert fiscal2.scoring_troll() == 150
    assert fiscal1.troll == True
    assert fiscal2.troll == False


