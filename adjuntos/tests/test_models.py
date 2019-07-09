import pytest
from django.db import IntegrityError
from elecciones.tests.factories import (
    AttachmentFactory,
    IdentificacionFactory,
    MesaFactory,
)
from adjuntos.models import Identificacion


def test_attachment_unico(db):
    a = AttachmentFactory()
    assert a.foto
    assert a.foto_digest
    with pytest.raises(IntegrityError):
        AttachmentFactory(foto=a.foto)


def test_identificacion_status_count(db):
    a = AttachmentFactory()
    AttachmentFactory()    # no fecta
    m1 = MesaFactory()
    m2 = MesaFactory()
    IdentificacionFactory(attachment=a, status='identificada', mesa=m1)
    IdentificacionFactory(attachment=a, status='spam', mesa=None)
    IdentificacionFactory(attachment=a, status='spam', mesa=None)
    IdentificacionFactory(attachment=a, status='invalida', mesa=None)
    IdentificacionFactory(attachment=a, status='identificada', mesa=m2)

    result = Identificacion.status_count(a)
    assert result == {
        (None, 'spam'): 2,
        (None, 'invalida'): 1,
        (m1.id, 'identificada'): 1,
        (m2.id, 'identificada'): 1,
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


