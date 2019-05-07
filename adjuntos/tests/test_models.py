import pytest
from django.db import IntegrityError
from elecciones.tests.factories import (
    AttachmentFactory,
)


def test_attachment_unico(db):
    a = AttachmentFactory()
    assert a.foto
    assert a.foto_digest
    with pytest.raises(IntegrityError):
        AttachmentFactory(foto=a.foto)

