import pytest

from django.conf import settings

from antitrolling.models import (
    EventoScoringTroll, CambioEstadoTroll,
    aumentar_scoring_troll_identificacion, aumentar_scoring_troll_carga
)
from elecciones.models import MesaCategoria

from elecciones.tests.factories import (
    MesaFactory, AttachmentFactory
)

from .utils_para_test import (
    nuevo_fiscal, identificar, reportar_problema_attachment,
    nueva_categoria, nueva_carga
)


def test_aplicar_marca_troll(db):
    fiscal = nuevo_fiscal()
    assert not fiscal.troll 
    fiscal.aplicar_marca_troll()
    assert fiscal.troll


def test_quitar_marca_troll(db):
    settings.SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL = 300
    
    fiscal = nuevo_fiscal()
    usuario_experto = nuevo_fiscal()
    assert not fiscal.troll

    # aumento el scoring x identificacion, para forzarlo a pasar a troll por scoring
    attach = AttachmentFactory()
    identi = reportar_problema_attachment(attach, fiscal)
    aumentar_scoring_troll_identificacion(400, identi)
    assert fiscal.troll

    # le saco la marca troll dejandolo en 150
    fiscal.quitar_marca_troll(usuario_experto, 150)

    # reviso status troll, scoring troll, y eventos
    assert not fiscal.troll
    assert fiscal.scoring_troll() == 150
    eventos = list(fiscal.eventos_scoring_troll.order_by('created').all())
    assert len(eventos) == 2
    primer_evento = eventos[0]
    assert primer_evento.motivo == EventoScoringTroll.MOTIVOS.identificacion_attachment_distinta_a_confirmada
    assert primer_evento.automatico
    assert primer_evento.actor is None
    assert primer_evento.fiscal_afectado == fiscal
    assert primer_evento.variacion == 400
    segundo_evento = eventos[1]
    assert segundo_evento.motivo == EventoScoringTroll.MOTIVOS.remocion_marca_troll
    assert not segundo_evento.automatico
    assert segundo_evento.actor == usuario_experto
    assert segundo_evento.fiscal_afectado == fiscal
    assert segundo_evento.variacion == -250

    # reviso cambios de estado
    cambios_estado = list(fiscal.cambios_estado_troll.order_by('created').all())
    assert len(cambios_estado) == 2
    primer_cambio_estado = cambios_estado[0]
    assert primer_cambio_estado.automatico
    assert primer_cambio_estado.actor is None
    assert primer_cambio_estado.evento_disparador == primer_evento
    assert primer_cambio_estado.troll
    segundo_cambio_estado = cambios_estado[1]
    assert not segundo_cambio_estado.automatico
    assert segundo_cambio_estado.actor == usuario_experto
    assert segundo_cambio_estado.evento_disparador == segundo_evento
    assert not segundo_cambio_estado.troll


def test_registro_evento_scoring_identificacion(db):
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
    assert evento.motivo == EventoScoringTroll.MOTIVOS.identificacion_attachment_distinta_a_confirmada
    assert evento.mesa_categoria is None
    assert evento.attachment == attach
    assert evento.automatico
    assert evento.actor is None
    assert evento.fiscal_afectado == fiscal
    assert evento.variacion == 100



def test_registro_evento_scoring_carga(db):
    """
    Se comprueba que un EventoScoringTroll se genere con los valores correctos.
    """

    # creo escenario
    fiscal = nuevo_fiscal()
    categoria = nueva_categoria(["o1", "o2", "o3"])
    mesa = MesaFactory(categorias=[categoria])
    mesa_categoria = MesaCategoria.objects.filter(mesa=mesa).first()
    carga = nueva_carga(mesa_categoria, fiscal, [30, 20, 10])

    assert fiscal.eventos_scoring_troll.count() == 0
    aumentar_scoring_troll_carga(42, carga, EventoScoringTroll.MOTIVOS.carga_valores_distintos_a_confirmados)
    assert fiscal.eventos_scoring_troll.count() == 1
    evento = fiscal.eventos_scoring_troll.first()
    assert evento.motivo == EventoScoringTroll.MOTIVOS.carga_valores_distintos_a_confirmados
    assert evento.mesa_categoria == mesa_categoria
    assert evento.attachment is None
    assert evento.automatico
    assert evento.actor is None
    assert evento.fiscal_afectado == fiscal
    assert evento.variacion == 42



def test_registro_cambio_estado_troll(db):
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
    assert cambioEstado.automatico
    assert cambioEstado.actor is None
    assert cambioEstado.evento_disparador == fiscal.eventos_scoring_troll.order_by('created').last()
    assert cambioEstado.troll



def test_aumentar_scrolling(db):
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
    assert not fiscal1.troll 
    assert not fiscal2.troll 

    attach3 = AttachmentFactory()
    identi4 = reportar_problema_attachment(attach3, fiscal1)
    aumentar_scoring_troll_identificacion(80, identi4)
    assert fiscal1.scoring_troll() == 430
    assert fiscal2.scoring_troll() == 150
    assert fiscal1.troll
    assert not fiscal2.troll 


def test_marcar_explicitamente_como_troll(db):
    """
    Se comprueba que al marcar explicitamente a un fiscal como troll, el efecto sea el esperado
    """

    fiscal = nuevo_fiscal()
    usuario_experto = nuevo_fiscal()
    assert not fiscal.troll 

    fiscal.marcar_como_troll(usuario_experto)
    assert fiscal.troll
    assert fiscal.scoring_troll() == 0
    eventos = list(fiscal.eventos_scoring_troll.order_by('created').all())
    assert len(eventos) == 1
    primer_evento = eventos[0]
    assert primer_evento.motivo == EventoScoringTroll.MOTIVOS.marca_explicita_troll
    assert not primer_evento.automatico 
    assert primer_evento.actor == usuario_experto
    assert primer_evento.fiscal_afectado == fiscal
    assert primer_evento.variacion == 0
    cambios_estado = list(fiscal.cambios_estado_troll.order_by('created').all())
    assert len(cambios_estado) == 1
    cambio_estado = cambios_estado[0]
    assert not cambio_estado.automatico 
    assert cambio_estado.actor == usuario_experto
    assert cambio_estado.evento_disparador == primer_evento
    assert cambio_estado.troll
