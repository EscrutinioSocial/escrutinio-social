import pytest
from django.db import IntegrityError
from elecciones.tests.factories import (
    AttachmentFactory,
    MesaFactory,
    IdentificacionFactory,
)
from django.utils import timezone
from adjuntos.models import Attachment, Identificacion
from adjuntos.consolidacion import consumir_novedades_identificacion


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
    assert set(Attachment.sin_identificar()) == {a1, a2, a3}
    a3.taken = timezone.now()
    a3.save()
    assert set(Attachment.sin_identificar()) == {a1, a2}


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
    IdentificacionFactory(attachment=a, status='spam', mesa=None)
    IdentificacionFactory(attachment=a, status='spam', mesa=None)
    IdentificacionFactory(attachment=a, status='invalida', mesa=None)

    # un estado excepcional, pero eventualmente posible?
    IdentificacionFactory(attachment=a, status='spam', mesa=m1)

    IdentificacionFactory(attachment=a, status='identificada', mesa=m2)

    result = a.status_count()
    assert sorted(result) == sorted([
        (0, 'spam', 2, 0),
        (0, 'invalida', 1, 0),
        (m1.id, 'identificada', 1, 0),
        (m2.id, 'identificada', 1, 0),
        (m1.id, 'spam', 1, 0)
    ])


def test_identificacion_consolidada_ninguno(db):
    a = AttachmentFactory()
    m1 = MesaFactory()
    IdentificacionFactory(attachment=a, status='identificada', mesa=m1)
    IdentificacionFactory(attachment=a, status='spam', mesa=None)
    IdentificacionFactory(attachment=a, status='spam', mesa=None)

    assert a.identificacion_testigo is None

    cant_novedades = Identificacion.objects.filter(procesada=False).count()
    assert cant_novedades == 3
    consumir_novedades_identificacion()

    cant_novedades = Identificacion.objects.filter(procesada=False).count()
    assert cant_novedades == 0

    assert a.identificacion_testigo is None


def test_identificacion_consolidada_alguna(db):
    a = AttachmentFactory()
    m1 = MesaFactory()
    i1 = IdentificacionFactory(attachment=a, status='identificada', mesa=m1)
    IdentificacionFactory(attachment=a, status='spam', mesa=None)
    IdentificacionFactory(attachment=a, status='spam', mesa=None)
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
