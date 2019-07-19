import pytest
from django.db import IntegrityError
from elecciones.tests.factories import (
    AttachmentFactory,
    MesaFactory,
    IdentificacionFactory,
    ProblemaFactory,
    FiscalFactory
)
from adjuntos.models import Attachment, Identificacion
from adjuntos.consolidacion import consumir_novedades_identificacion
from problemas.models import ReporteDeProblema, Problema


def test_attachment_unico(db):
    a = AttachmentFactory()
    assert a.foto
    assert a.foto_digest
    with pytest.raises(IntegrityError):
        AttachmentFactory(foto=a.foto)


def test_sin_identificar_excluye_taken(db):
    a1 = IdentificacionFactory(status='identificada').attachment
    a2 = IdentificacionFactory(status='spam').attachment
    a3 = IdentificacionFactory(status='spam').attachment
    assert set(Attachment.sin_identificar_con_timeout()) == {a1, a2, a3}
    a3.take()
    assert set(Attachment.sin_identificar_con_timeout(wait=2)) == {a1, a2}


def test_sin_identificar_excluye_otros_estados(db):
    AttachmentFactory(status='spam')
    AttachmentFactory(status='invalida')
    AttachmentFactory(status='identificada')
    a = AttachmentFactory(status=Attachment.STATUS.sin_identificar)
    assert set(Attachment.sin_identificar()) == {a}


def test_identificacion_status_count(db):
    a = AttachmentFactory()
    AttachmentFactory()    # no fecta
    m1 = MesaFactory()
    m2 = MesaFactory()
    IdentificacionFactory(attachment=a, status='identificada', mesa=m1)
    IdentificacionFactory(attachment=a, status='problema', mesa=None)
    IdentificacionFactory(attachment=a, status='problema', mesa=None)
    IdentificacionFactory(attachment=a, status='invalida', mesa=None)

    # un estado excepcional, pero eventualmente posible?
    IdentificacionFactory(attachment=a, status='problema', mesa=m1)

    IdentificacionFactory(attachment=a, status='identificada', mesa=m2)

    result = a.status_count(Identificacion.STATUS.identificada)
    assert sorted(result) == sorted([
        (m1.id, 1, 0),
        (m2.id, 1, 0),
    ])

    result = a.status_count(Identificacion.STATUS.problema)
    assert sorted(result) == sorted([
        (0, 2, 0),
        (m1.id, 1, 0)
    ])

def test_identificacion_consolidada_ninguno(db):
    a = AttachmentFactory()
    m1 = MesaFactory()
    IdentificacionFactory(attachment=a, status='identificada', mesa=m1)

    i1 = IdentificacionFactory(attachment=a, status='problema', mesa=None)
    f = FiscalFactory()
    Problema.reportar_problema(f, 'reporte 1', 
        ReporteDeProblema.TIPOS_DE_PROBLEMA.spam, identificacion=i1)
    assert i1.problemas.first().problema.estado == Problema.ESTADOS.potencial

    i2 = IdentificacionFactory(attachment=a, status='problema', mesa=None)
    Problema.reportar_problema(f, 'reporte 1', 
        ReporteDeProblema.TIPOS_DE_PROBLEMA.ilegible, identificacion=i2)

    assert a.identificacion_testigo is None

    cant_novedades = Identificacion.objects.filter(procesada=False).count()
    assert cant_novedades == 3
    consumir_novedades_identificacion()
    assert i1.problemas.first().problema.estado == Problema.ESTADOS.pendiente

    cant_novedades = Identificacion.objects.filter(procesada=False).count()
    assert cant_novedades == 0

    assert a.identificacion_testigo is None


def test_identificacion_consolidada_alguna(db):
    a = AttachmentFactory()
    m1 = MesaFactory()
    i1 = IdentificacionFactory(attachment=a, status='identificada', mesa=m1)
    IdentificacionFactory(attachment=a, status='problema', mesa=None)
    IdentificacionFactory(attachment=a, status='problema', mesa=None)
    IdentificacionFactory(attachment=a, status='identificada', mesa=m1)

    assert a.identificacion_testigo is None

    cant_novedades = Identificacion.objects.filter(procesada=False).count()
    assert cant_novedades == 4
    consumir_novedades_identificacion()

    cant_novedades = Identificacion.objects.filter(procesada=False).count()
    assert cant_novedades == 0

    a.refresh_from_db()
    assert a.identificacion_testigo == i1
    assert a.mesa == m1
    assert a.status == Attachment.STATUS.identificada


def test_identificacion_consolidada_con_minimo_1(db, settings):
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 1
    a = AttachmentFactory()
    m1 = MesaFactory()
    i1 = IdentificacionFactory(attachment=a, status='identificada', mesa=m1)
    consumir_novedades_identificacion()
    a.refresh_from_db()
    assert a.identificacion_testigo == i1
    assert a.mesa == m1
    assert a.status == Attachment.STATUS.identificada
