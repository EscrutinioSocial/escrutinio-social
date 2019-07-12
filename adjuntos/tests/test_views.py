from elecciones.tests.factories import (
    AttachmentFactory,
    MesaFactory,
)
from django.urls import reverse
from elecciones.tests.test_resultados import fiscal_client  # noqa
from adjuntos.views import NINGUN_ATTACHMENT_VALIDO_MESSAGE
import os 

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
    assert i.mesa == m1
    assert i.fiscal == admin_user.fiscal
    assert not i.consolidada
    # la identificacion todavia no está consolidada
    assert not m1.attachments.exists()


def test_identificacion_problema_create_view_post(fiscal_client, admin_user):
    m1 = MesaFactory()
    a = AttachmentFactory()
    data = {
        'status': 'spam',
    }
    response = fiscal_client.post(reverse('asignar-problema', args=[a.id]), data)
    assert response.status_code == 302
    assert response.url == reverse("elegir-adjunto")
    assert a.identificaciones.count() == 1
    i = a.identificaciones.first()
    assert i.status == 'spam'
    assert i.fiscal == admin_user.fiscal
    assert i.mesa is None
    assert not i.consolidada
    # mesa no tiene attach aun
    assert not m1.attachments.exists()


def test_subir_adjunto_unidad_basica_no_file(fiscal_client):
    data = {}
    response = fiscal_client.post(reverse('agregar-adjuntos-ub'))

    assert response.status_code == 200
    form_errors = response.context['form'].errors 
    
    assert len(form_errors) == 1
    assert len(form_errors['file_field']) == 1
    assert form_errors['file_field'][0] == "This field is required."

def test_subir_adjunto_unidad_basica_no_imagen(fiscal_client):
    este_directorio = os.path.dirname(os.path.realpath(__file__))
    no_imagen = open(os.path.join(este_directorio, 'archivo_no_imagen.txt'),'r') 
    data = { 'file_field' : no_imagen}
    response = fiscal_client.post(reverse('agregar-adjuntos-ub'), data)
    print(response.context['form'])

    assert response.status_code == 200
    form_errors = response.context['form'].errors 
    
    assert len(form_errors) == 1
    assert len(form_errors['file_field']) == 1
    assert form_errors['file_field'][0] == NINGUN_ATTACHMENT_VALIDO_MESSAGE


