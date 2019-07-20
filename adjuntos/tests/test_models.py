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
    Problema.reportar_problema(f, 'reporte 2', 
        ReporteDeProblema.TIPOS_DE_PROBLEMA.ilegible, identificacion=i2)

    assert a.identificacion_testigo is None

    cant_novedades = Identificacion.objects.filter(procesada=False).count()
    assert cant_novedades == 3
    consumir_novedades_identificacion()

    # Se consolidó un problema.
    assert i1.problemas.first().problema.estado == Problema.ESTADOS.pendiente

    cant_novedades = Identificacion.objects.filter(procesada=False).count()
    assert cant_novedades == 0

    assert a.identificacion_testigo is None


def test_identificacion_consolidada_alguna(db):
    a = AttachmentFactory()
    m1 = MesaFactory()
    i1 = IdentificacionFactory(attachment=a, status='identificada', mesa=m1)
    IdentificacionFactory(attachment=a, status='problema', mesa=None)
    i2 = IdentificacionFactory(attachment=a, status='problema', mesa=None)
    Problema.reportar_problema(FiscalFactory(), 'reporte 1', 
        ReporteDeProblema.TIPOS_DE_PROBLEMA.ilegible, identificacion=i2)
    IdentificacionFactory(attachment=a, status='identificada', mesa=m1)

    assert a.identificacion_testigo is None

    cant_novedades = Identificacion.objects.filter(procesada=False).count()
    assert cant_novedades == 4
    consumir_novedades_identificacion()

    # No se consolidó el problema.
    assert i2.problemas.first().problema.estado == Problema.ESTADOS.potencial

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

def test_ciclo_de_vida_problemas_resolver(db):
    a = AttachmentFactory()
    m1 = MesaFactory()
    IdentificacionFactory(attachment=a, status='identificada', mesa=m1)

    # Está pendiente.
    assert a in Attachment.sin_identificar()

    i1 = IdentificacionFactory(attachment=a, status='problema', mesa=None)
    f = FiscalFactory()
    Problema.reportar_problema(f, 'reporte 1', 
        ReporteDeProblema.TIPOS_DE_PROBLEMA.spam, identificacion=i1)
    assert i1.problemas.first().problema.estado == Problema.ESTADOS.potencial

    i2 = IdentificacionFactory(attachment=a, status='problema', mesa=None)
    Problema.reportar_problema(f, 'reporte 2', 
        ReporteDeProblema.TIPOS_DE_PROBLEMA.ilegible, identificacion=i2)

    assert i1.invalidada == False
    assert i2.invalidada == False

    consumir_novedades_identificacion()

    # Se consolidó un problema.
    a.refresh_from_db()
    assert a.status == Attachment.STATUS.problema
    problema = i1.problemas.first().problema
    assert problema.estado == Problema.ESTADOS.pendiente

    # El attach no está entre los pendientes.
    assert a not in Attachment.sin_identificar()

    problema.resolver(FiscalFactory().user)

    assert problema.estado == Problema.ESTADOS.resuelto

    i1.refresh_from_db()
    i2.refresh_from_db()
    # Las identificaciones están invalidadas.
    assert i1.invalidada == True
    assert i2.invalidada == True

    consumir_novedades_identificacion()

    # Se agrega una nueva identificación y se consolida.
    IdentificacionFactory(attachment=a, status='identificada', mesa=m1)
    consumir_novedades_identificacion()
    a.refresh_from_db()
    assert a.status == Attachment.STATUS.identificada
    assert a.mesa == m1

def test_ciclo_de_vida_problemas_descartar(db):
    a = AttachmentFactory()
    m1 = MesaFactory()
    IdentificacionFactory(attachment=a, status='identificada', mesa=m1)

    i1 = IdentificacionFactory(attachment=a, status='problema', mesa=None)
    f = FiscalFactory()
    Problema.reportar_problema(f, 'reporte 1', 
        ReporteDeProblema.TIPOS_DE_PROBLEMA.spam, identificacion=i1)
    assert i1.problemas.first().problema.estado == Problema.ESTADOS.potencial

    i2 = IdentificacionFactory(attachment=a, status='problema', mesa=None)
    Problema.reportar_problema(f, 'reporte 2', 
        ReporteDeProblema.TIPOS_DE_PROBLEMA.ilegible, identificacion=i2)

    assert i1.invalidada == False
    assert i2.invalidada == False

    consumir_novedades_identificacion()

    # Se consolidó un problema.
    a.refresh_from_db()
    assert a.status == Attachment.STATUS.problema
    problema = i1.problemas.first().problema
    assert problema.estado == Problema.ESTADOS.pendiente

    problema.descartar(FiscalFactory().user)

    assert problema.estado == Problema.ESTADOS.descartado

    i1.refresh_from_db()
    i2.refresh_from_db()
    # Las identificaciones están invalidadas.
    assert i1.invalidada == True
    assert i2.invalidada == True

    consumir_novedades_identificacion()

    # Se agrega una nueva identificación y se consolida.
    IdentificacionFactory(attachment=a, status='identificada', mesa=m1)
    consumir_novedades_identificacion()
    a.refresh_from_db()
    assert a.status == Attachment.STATUS.identificada
    assert a.mesa == m1
