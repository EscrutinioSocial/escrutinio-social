import pytest

from django.conf import settings

from antitrolling.models import (
    EventoScoringTroll, CambioEstadoTroll,
    aumentar_scoring_troll_identificacion, efecto_scoring_troll_asociacion_attachment
)

from elecciones.tests.factories import (
    UserFactory, FiscalFactory, 
    MesaFactory, AttachmentFactory, IdentificacionFactory
)


def nuevo_fiscal():
    usuario = UserFactory()
    fiscal = FiscalFactory(user=usuario)
    return fiscal

def identificar(attach, mesa, fiscal):
    return IdentificacionFactory(
        status='identificada',
        attachment=attach,
        mesa=mesa,
        fiscal=fiscal
    )

def reportar_problema_attachment(attach, fiscal):
    return IdentificacionFactory(
        status='problema',
        attachment=attach,
        fiscal=fiscal
    )


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

