import pytest
from constance.test import override_config
from django.conf import settings

from elecciones.models import MesaCategoria, Carga, CargasIncompatiblesError
from adjuntos.models import Identificacion, Attachment
from adjuntos.consolidacion import consumir_novedades
from antitrolling.efecto import (
  efecto_scoring_troll_asociacion_attachment, efecto_scoring_troll_confirmacion_carga
)
from antitrolling.models import EventoScoringTroll
from elecciones.tests.factories import (
    MesaFactory, AttachmentFactory, MesaCategoriaFactory, IdentificacionFactory,
    FiscalFactory
)

from .utils_para_test import (
    nuevo_fiscal, identificar, reportar_problema_attachment,
    nueva_categoria, nueva_carga
)
from problemas.models import Problema, ReporteDeProblema


def test_efecto_consolidar_asociacion_attachment(db, settings):
    """
    Se comprueba que el efecto de afectar el scoring de troll a partir de la asociacion
    de un Attachment a una Mesa sea el correcto.
    O sea, que se aumente el scoring de los fiscales que hicieron identificaciones distintas
    a la aceptada, y que no aumente el scoring de los fiscales que hicieron la identificacion aceptada.
    """
    with override_config(SCORING_TROLL_IDENTIFICACION_DISTINTA_A_CONFIRMADA = 180, SCORING_TROLL_DESCUENTO_ACCION_CORRECTA = 40):
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

        for fiscal in [fiscal_1, fiscal_2, fiscal_3, fiscal_4]:
            fiscal.refresh_from_db()
        assert EventoScoringTroll.objects.count() == cantidad_eventos_antes + 4
        assert fiscal_1.scoring_troll() == -40
        assert fiscal_2.scoring_troll() == -40
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
    assert carga_1 - carga_2 == 4


def test_diferencia_opciones_cargas_incompatibles(db):
    # creo fiscales
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()

    # creo opciones y categoria
    categoria_1 = nueva_categoria(["o1", "o2", "o3"])
    categoria_2 = nueva_categoria(["p1", "p2", "p3"])

    # creo mesa y mesa_categoria
    mesa = MesaFactory(categorias=[categoria_1, categoria_2])
    mesa_categoria_1 = MesaCategoria.objects.filter(mesa=mesa, categoria=categoria_1).first()
    mesa_categoria_2 = MesaCategoria.objects.filter(mesa=mesa, categoria=categoria_2).first()

    # creo cargas
    carga_1 = nueva_carga(mesa_categoria_1, fiscal_1, [30, 20, 10])
    carga_2 = nueva_carga(mesa_categoria_2, fiscal_2, [28, 19, 11])

    # verifico error
    with pytest.raises(CargasIncompatiblesError) as e:
        carga_1 - carga_2
    assert 'las cargas no coinciden en mesa, categoría o tipo' in str(e.value)


def test_diferencia_opciones_con_opciones_diferentes(db):
    # creo fiscales
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()

    # creo opciones y categoria
    categoria = nueva_categoria(["o1", "o2", "o3"])

    # creo mesa y mesa_categoria
    mesa = MesaFactory(categorias=[categoria])
    mesa_categoria = MesaCategoria.objects.filter(mesa=mesa).first()

    # creo cargas, a la segunda le falta un valor, por lo que se van a agregar sólo dos VotoReportadoMesa
    carga_1 = nueva_carga(mesa_categoria, fiscal_1, [30, 20, 10])
    carga_2 = nueva_carga(mesa_categoria, fiscal_2, [28, 19])

    # verifico error
    with pytest.raises(CargasIncompatiblesError) as e:
        carga_1 - carga_2
    assert 'las cargas no coinciden en sus opciones' in str(e.value)


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
    for fiscal in [fiscal_1, fiscal_2, fiscal_3, fiscal_4]:
        fiscal.refresh_from_db()
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
    carga_3_1_4 = nueva_carga(mesa_categoria_3_1, fiscal_4, [30, 20, 10])

    assert Identificacion.objects.filter(invalidada=True).count() == 0
    assert Carga.objects.filter(invalidada=True).count() == 0
    assert Identificacion.objects.filter(fiscal=fiscal_1).count() == 2
    assert Carga.objects.filter(fiscal=fiscal_1).count() == 3

    # hacemos una marca explicita de troll, tienen que quedar invalidadas las cargas e identificaciones que hizo,
    # y ninguna mas
    fiscal_1.marcar_como_troll(fiscal_4)
    assert Identificacion.objects.filter(invalidada=True).count() == 2
    assert Carga.objects.filter(invalidada=True).count() == 3
    for ident in Identificacion.objects.filter(fiscal=fiscal_1):
        assert ident.invalidada
    for carga in Carga.objects.filter(fiscal=fiscal_1):
        assert carga.invalidada


def test_efecto_de_ser_troll(db):
    """
    Se comprueba que las cargas e identificaciones que realiza un fiscal
    luego de ser detectado como troll, nacen invalidadas y procesadas.
    """
    # escenario
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    categoria = nueva_categoria(["o1", "o2", "o3"])
    mesa = MesaFactory(categorias=[categoria])
    mesa_categoria = MesaCategoria.objects.filter(mesa=mesa).first()
    attach_1 = AttachmentFactory()
    attach_2 = AttachmentFactory()

    # marco al fiscal_1 como troll
    fiscal_1.marcar_como_troll(fiscal_2)

    # despues, una carga, una identificacion y un reporte de problema cada uno
    ident_1 = identificar(attach_1, mesa, fiscal_1)
    ident_2 = identificar(attach_1, mesa, fiscal_2)
    problema_1 = reportar_problema_attachment(attach_2, fiscal_1)
    problema_2 = reportar_problema_attachment(attach_2, fiscal_2)
    carga_1 = nueva_carga(mesa_categoria, fiscal_1, [30, 20, 10])
    carga_2 = nueva_carga(mesa_categoria, fiscal_2, [30, 20, 10])

    # las cargas e identificaciones que hizo el fiscal 1 estan invalidadas y procesadas,
    # las que hizo el fiscal 2 no
    for accion in [ident_1, problema_1, carga_1]:
        assert accion.invalidada
        assert accion.procesada
    for accion in [ident_2, problema_2, carga_2]:
        assert not accion.invalidada
        assert not accion.procesada

    # consolido cargas e identificaciones. Ni el attachment ni la mesa_categoria deberian estar consolidados.
    consumir_novedades()
    for db_object in [mesa_categoria, attach_1, attach_2]:
        db_object.refresh_from_db()
    assert mesa_categoria.status == MesaCategoria.STATUS.total_sin_consolidar
    assert attach_1.status == Attachment.STATUS.sin_identificar
    assert attach_2.status == Attachment.STATUS.sin_identificar


def test_efecto_ignora_cargas_incompatibles(db, caplog):
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    mesa_categoria = MesaCategoriaFactory()
    carga_1 = nueva_carga(mesa_categoria, fiscal_1, [30, 20, 10])
    carga_1.actualizar_firma()
    mesa_categoria.carga_testigo = carga_1
    mesa_categoria.save()

    # incompatible
    carga_2 = nueva_carga(mesa_categoria, fiscal_2, [30, 20])
    carga_2.actualizar_firma()
    efecto_scoring_troll_confirmacion_carga(mesa_categoria)

    # se ignoran las diferencias, no afecta
    assert EventoScoringTroll.objects.count() == 0


def test_efecto_diferencia_1(db, caplog):
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    mesa_categoria = MesaCategoriaFactory()
    carga_1 = nueva_carga(mesa_categoria, fiscal_1, [30, 20, 10])
    carga_1.actualizar_firma()
    mesa_categoria.carga_testigo = carga_1
    mesa_categoria.save()

    # incompatible
    carga_2 = nueva_carga(mesa_categoria, fiscal_2, [30, 20, 9])
    carga_2.actualizar_firma()
    efecto_scoring_troll_confirmacion_carga(mesa_categoria)
    # hay un sólo evento troll y la diferencia es 1
    assert EventoScoringTroll.objects.get().variacion == carga_1 - carga_2 == 1

def test_efecto_problema_descartado(db):
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()

    a = AttachmentFactory()
    m1 = MesaFactory()
    i1 = IdentificacionFactory(attachment=a, status='problema', mesa=None)
    f = FiscalFactory()
    Problema.reportar_problema(fiscal_1, 'reporte 1', 
        ReporteDeProblema.TIPOS_DE_PROBLEMA.spam, identificacion=i1)
    assert i1.problemas.first().problema.estado == Problema.ESTADOS.potencial

    problema = i1.problemas.first().problema
    problema.descartar(nuevo_fiscal().user)

    from constance import config
    assert EventoScoringTroll.objects.get().variacion == config.SCORING_TROLL_PROBLEMA_DESCARTADO
