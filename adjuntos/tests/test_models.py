import pytest
from django.db import IntegrityError
from elecciones.tests.factories import (
    AttachmentFactory,
    MesaFactory,
    IdentificacionFactory,
)
from django.utils import timezone
from adjuntos.models import Attachment


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

    i2 = IdentificacionFactory(attachment=a, status='identificada', mesa=m2)

    result = a.status_count()
    assert result == {
        (None, 'spam'): 2,
        (None, 'invalida'): 1,
        (m1.id, 'identificada'): 1,
        (m2.id, 'identificada'): 1,
        (m1.id, 'spam'): 1,
    }

    result = a.status_count(exclude=i2.id)
    assert result == {
        (None, 'spam'): 2,
        (None, 'invalida'): 1,
        (m1.id, 'identificada'): 1,
        (m1.id, 'spam'): 1,
    }


def test_identificacion_consolidada(db):
    a = AttachmentFactory()
    m1 = MesaFactory()
    i1 = IdentificacionFactory(attachment=a, status='identificada', mesa=m1)
    i2 = IdentificacionFactory(attachment=a, status='spam', mesa=None)
    i3 = IdentificacionFactory(attachment=a, status='spam', mesa=None)

    assert not i1.consolidada
    assert not i2.consolidada
    assert i3.consolidada
