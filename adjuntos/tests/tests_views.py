from elecciones.tests.factories import (
    AttachmentFactory,
    MesaFactory,
)
from django.urls import reverse
from elecciones.tests.test_resultados import fiscal_client  # noqa


def test_identificacion_create_view_get(fiscal_client):
    a = AttachmentFactory()
    response = fiscal_client.get(reverse('asignar-mesa', args=[a.id]))
    assert response.status_code == 200
    assert a.foto.url in a.foto.url in response.content.decode('utf8')


def test_identificacion_create_view_post(fiscal_client, admin_user):
    m1 = MesaFactory()
    a = AttachmentFactory()
    data = {
        'mesa': m1.id,
        'circuito': m1.circuito.id,
        'seccion': m1.circuito.seccion.id,
        'distrito': m1.circuito.seccion.distrito.id,
    }
    response = fiscal_client.post(reverse('asignar-mesa', args=[a.id]), data)
    assert response.status_code == 302
    assert response.url == reverse("elegir-adjunto")
    assert a.identificaciones.count() == 1
    i = a.identificaciones.first()
    assert i.status == 'identificada'
    assert i.fiscal == admin_user.fiscal
    assert not i.consolidada
    assert list(m1.attachments.all()) == [a]
