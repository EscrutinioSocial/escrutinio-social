from elecciones.tests.factories import (
    MesaFactory,
    IdentificacionFactory,
)

from adjuntos.models import Identificacion
from adjuntos.models import Attachment

from adjuntos.consolidacion import consolidar_identificaciones

def test_consolidacion__con_mesa_id(db):
    """
    Este test ataca el caso donde a la consolidacion de la identificación ya le pasamos un mesa_id.
    Esto se puede dar en cargas desde una Unidad Básica
    """
    mesa1 = MesaFactory()
    identificacion = IdentificacionFactory(status=Identificacion.STATUS.identificada, mesa=mesa1)
    attachment = identificacion.attachment

    assert attachment.identificacion_testigo is None
    assert attachment.mesa is None
    assert attachment.status == Attachment.STATUS.sin_identificar

    consolidar_identificaciones(attachment, mesa1.id)

    assert attachment.identificacion_testigo == identificacion
    assert attachment.mesa == mesa1
    assert attachment.status == Attachment.STATUS.identificada

